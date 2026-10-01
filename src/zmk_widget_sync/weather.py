from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime

from .config import WeatherConfig
from .models import WeatherData

API_URL = "https://api.open-meteo.com/v1/forecast"

CONDITIONS = {
    0: "Bezchmurnie",
    1: "Pogodnie",
    2: "Chmury",
    3: "Pochmurno",
    45: "Mgla",
    48: "Szron",
    51: "Mzawka",
    53: "Mzawka",
    55: "Mzawka",
    56: "Marzn. deszcz",
    57: "Marzn. deszcz",
    61: "Deszcz",
    63: "Deszcz",
    65: "Ulewa",
    66: "Marzn. deszcz",
    67: "Marzn. deszcz",
    71: "Snieg",
    73: "Snieg",
    75: "Sniezyca",
    77: "Krupa sniezna",
    80: "Przelotny deszcz",
    81: "Przelotny deszcz",
    82: "Silna ulewa",
    85: "Przelotny snieg",
    86: "Silny snieg",
    95: "Burza",
    96: "Burza z gradem",
    99: "Burza z gradem",
}


def parse_response(payload: dict, location: str) -> WeatherData:
    current = payload["current"]
    code = int(current["weather_code"])
    current_time = datetime.fromisoformat(current["time"])
    probability = 0

    hourly = payload.get("hourly", {})
    times = hourly.get("time", [])
    probabilities = hourly.get("precipitation_probability", [])
    if times and probabilities:
        nearest = min(range(len(times)), key=lambda index: abs(datetime.fromisoformat(times[index]) - current_time))
        probability = int(probabilities[nearest] or 0)

    return WeatherData(
        temperature_tenths=round(float(current["temperature_2m"]) * 10),
        weather_code=code,
        precipitation_probability=max(0, min(100, probability)),
        location=location,
        condition=CONDITIONS.get(code, "Pogoda"),
    )


def fetch_weather(config: WeatherConfig, timeout: float = 15.0) -> WeatherData:
    query = urllib.parse.urlencode(
        {
            "latitude": config.latitude,
            "longitude": config.longitude,
            "current": "temperature_2m,weather_code",
            "hourly": "precipitation_probability",
            "forecast_days": 1,
            "timezone": "auto",
        }
    )
    request = urllib.request.Request(f"{API_URL}?{query}", headers={"User-Agent": "zmk-widget-sync/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.load(response)
    return parse_response(payload, config.location)
