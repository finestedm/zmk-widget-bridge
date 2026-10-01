import unittest

from zmk_widget_sync.weather import parse_response


class WeatherTests(unittest.TestCase):
    def test_nearest_hour_probability(self):
        payload = {
            "current": {"time": "2026-10-01T12:20", "temperature_2m": 8.7, "weather_code": 3},
            "hourly": {
                "time": ["2026-10-01T11:00", "2026-10-01T12:00", "2026-10-01T13:00"],
                "precipitation_probability": [5, 30, 70],
            },
        }
        result = parse_response(payload, "Warszawa")
        self.assertEqual(result.temperature_tenths, 87)
        self.assertEqual(result.precipitation_probability, 30)
        self.assertEqual(result.condition, "Pochmurno")


if __name__ == "__main__":
    unittest.main()
