from __future__ import annotations

import asyncio
import logging
import time

from bleak import BleakClient

from .config import AppConfig
from .google_calendar import fetch_events
from .models import DisplayData
from .protocol import encode_packet
from .transport import resolve_device, write_packet
from .weather import fetch_weather

LOG = logging.getLogger(__name__)


class SyncState:
    def __init__(self) -> None:
        self.data = DisplayData()
        self.weather_due = 0.0
        self.calendar_due = 0.0
        self.sequence = 0

    async def refresh(self, config: AppConfig, force: bool = False) -> None:
        now = time.monotonic()
        if config.weather.enabled and (force or now >= self.weather_due):
            try:
                self.data.weather = await asyncio.to_thread(fetch_weather, config.weather)
                self.weather_due = now + config.sync.weather_refresh_seconds
            except Exception:
                LOG.exception("Weather refresh failed; retaining the previous value")
                self.weather_due = now + min(60, config.sync.weather_refresh_seconds)

        if config.calendar.enabled and (force or now >= self.calendar_due):
            try:
                self.data.events = await asyncio.to_thread(fetch_events, config.calendar)
                self.calendar_due = now + config.sync.calendar_refresh_seconds
            except Exception:
                LOG.exception("Calendar refresh failed; retaining the previous value")
                self.calendar_due = now + min(30, config.sync.calendar_refresh_seconds)

    def packet(self) -> tuple[int, bytes]:
        sequence = self.sequence
        packet = encode_packet(self.data, sequence)
        self.sequence = (self.sequence + 1) & 0xFF
        return sequence, packet


async def run_once(config: AppConfig, dry_run: bool = False) -> bytes:
    state = SyncState()
    await state.refresh(config, force=True)
    sequence, packet = state.packet()
    if not dry_run:
        target = await resolve_device(config.bluetooth)
        async with BleakClient(target, timeout=20.0) as client:
            await write_packet(client, packet, sequence)
    return packet


async def run_forever(config: AppConfig) -> None:
    state = SyncState()
    while True:
        try:
            target = await resolve_device(config.bluetooth)
            LOG.info("Connecting to %s", target)
            async with BleakClient(target, timeout=20.0) as client:
                LOG.info("Connected; widget synchronization is active")
                while client.is_connected:
                    await state.refresh(config)
                    sequence, packet = state.packet()
                    await write_packet(client, packet, sequence)
                    await asyncio.sleep(config.sync.heartbeat_seconds)
        except asyncio.CancelledError:
            raise
        except Exception:
            LOG.exception("Synchronization connection failed; retrying in 10 seconds")
            await asyncio.sleep(10)
