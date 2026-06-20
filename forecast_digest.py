import requests

HEADERS = {"User-Agent": "PythonWeatherScript/2.0", "Accept": "application/geo+json"}
TIMEOUT = 60


def get_forecast_digest(lat: float, lon: float, *, session: requests.Session = None) -> list[dict]:
    """Fetch next 6 NOAA forecast periods and return normalized dicts."""
    _session = session or requests.Session()

    points_url = f"https://api.weather.gov/points/{lat},{lon}"
    points_res = _session.get(points_url, headers=HEADERS, timeout=TIMEOUT)
    points_res.raise_for_status()
    forecast_url = points_res.json()["properties"]["forecast"]

    forecast_res = _session.get(forecast_url, headers=HEADERS, timeout=TIMEOUT)
    forecast_res.raise_for_status()
    periods = forecast_res.json()["properties"]["periods"][:6]

    digest = []
    for p in periods:
        wind_speed = p.get("windSpeed")
        wind_dir   = p.get("windDirection")
        wind = "N/A" if (wind_speed is None and wind_dir is None) else f"{wind_speed} {wind_dir}".strip()
        digest.append({
            "name":              p.get("name", "N/A"),
            "temperature":       p.get("temperature", "N/A"),
            "temp_unit":         p.get("temperatureUnit", "F"),
            "wind":              wind,
            "short_forecast":    p.get("shortForecast", "N/A"),
            "detailed_forecast": p.get("detailedForecast", "N/A"),
        })
    return digest