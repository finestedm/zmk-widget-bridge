from dataclasses import dataclass, field


@dataclass(frozen=True)
class WeatherData:
    temperature_tenths: int
    weather_code: int
    precipitation_probability: int
    location: str
    condition: str


@dataclass(frozen=True)
class CalendarEvent:
    time_label: str
    title: str


@dataclass
class DisplayData:
    weather: WeatherData | None = None
    events: list[CalendarEvent] = field(default_factory=list)
