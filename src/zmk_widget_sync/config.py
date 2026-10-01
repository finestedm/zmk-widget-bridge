from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


def default_config_path() -> Path:
    root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return root / "zmk-widget-sync" / "config.toml"


def _path(value: str) -> Path:
    return Path(value).expanduser()


@dataclass(frozen=True)
class BluetoothConfig:
    address: str = ""
    device_name: str = "FunkeeB_Corne"


@dataclass(frozen=True)
class SyncConfig:
    heartbeat_seconds: int = 30
    weather_refresh_seconds: int = 900
    calendar_refresh_seconds: int = 60


@dataclass(frozen=True)
class WeatherConfig:
    enabled: bool = True
    latitude: float = 0.0
    longitude: float = 0.0
    location: str = ""


@dataclass(frozen=True)
class CalendarConfig:
    enabled: bool = True
    credentials_file: Path = Path("credentials.json")
    token_file: Path = Path("token.json")
    calendar_ids: tuple[str, ...] = ("primary",)
    timezone: str = "UTC"
    max_events: int = 2


@dataclass(frozen=True)
class AppConfig:
    bluetooth: BluetoothConfig
    sync: SyncConfig
    weather: WeatherConfig
    calendar: CalendarConfig


def load_config(path: Path | None = None) -> AppConfig:
    path = path or default_config_path()
    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    bt = raw.get("bluetooth", {})
    sync = raw.get("sync", {})
    weather = raw.get("weather", {})
    calendar = raw.get("calendar", {})

    config = AppConfig(
        bluetooth=BluetoothConfig(
            address=str(bt.get("address", "")).strip(),
            device_name=str(bt.get("device_name", "FunkeeB_Corne")).strip(),
        ),
        sync=SyncConfig(
            heartbeat_seconds=int(sync.get("heartbeat_seconds", 30)),
            weather_refresh_seconds=int(sync.get("weather_refresh_seconds", 900)),
            calendar_refresh_seconds=int(sync.get("calendar_refresh_seconds", 60)),
        ),
        weather=WeatherConfig(
            enabled=bool(weather.get("enabled", True)),
            latitude=float(weather.get("latitude", 0.0)),
            longitude=float(weather.get("longitude", 0.0)),
            location=str(weather.get("location", "")).strip(),
        ),
        calendar=CalendarConfig(
            enabled=bool(calendar.get("enabled", True)),
            credentials_file=_path(str(calendar.get("credentials_file", "credentials.json"))),
            token_file=_path(str(calendar.get("token_file", "token.json"))),
            calendar_ids=tuple(calendar.get("calendar_ids", ["primary"])),
            timezone=str(calendar.get("timezone", "UTC")),
            max_events=max(0, min(2, int(calendar.get("max_events", 2)))),
        ),
    )

    if config.sync.heartbeat_seconds < 5:
        raise ValueError("sync.heartbeat_seconds must be at least 5")
    if config.weather.enabled and not (-90 <= config.weather.latitude <= 90):
        raise ValueError("weather.latitude must be between -90 and 90")
    if config.weather.enabled and not (-180 <= config.weather.longitude <= 180):
        raise ValueError("weather.longitude must be between -180 and 180")
    return config
