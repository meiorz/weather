import csv
from unittest.mock import Mock

import pytest
import requests

import forecast_digest
import geocode_location
import main
from config import GEOCODER_DEFAULT_USER_AGENT


class DummyResponse:
    def __init__(self, payload=None, status_error=None):
        self._payload = payload or {}
        self._status_error = status_error

    def raise_for_status(self):
        if self._status_error:
            raise self._status_error

    def json(self):
        return self._payload


def test_get_aqi_category_plain_and_rich():
    assert main.get_aqi_category(42) == "Good"
    assert main.get_aqi_category(75) == "Moderate"
    assert main.get_aqi_category(175) == "Unhealthy"
    assert "[green]Good[/green]" == main.get_aqi_category(42, rich=True)
    assert "Hazardous" == main.get_aqi_category(301)


def test_safe_get_nested_and_default():
    payload = {"a": {"b": {"c": 9}}}
    assert main.safe_get(payload, "a", "b", "c") == 9
    assert main.safe_get(payload, "a", "x", default="fallback") == "fallback"
    assert main.safe_get(None, "a", default="fallback") == "fallback"


def test_build_location_context_passes_user_agent(monkeypatch):
    seen = {}

    def fake_geocode(query, *, user_agent=None, timeout=20):
        seen["query"] = query
        seen["user_agent"] = user_agent
        return (37.77, -122.42)

    monkeypatch.setattr(main, "geocode_location", fake_geocode)
    ctx = main.build_location_context("San Francisco, CA", "student-app/1.0")
    assert ctx.name == "San Francisco, CA"
    assert ctx.lat == 37.77
    assert ctx.lon == 122.42 or ctx.lon == -122.42
    assert seen == {"query": "San Francisco, CA", "user_agent": "student-app/1.0"}


def test_geocode_location_uses_provided_user_agent(monkeypatch):
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        captured["timeout"] = timeout
        return DummyResponse([{"lat": "37.77", "lon": "-122.42"}])

    monkeypatch.setattr(geocode_location.requests, "get", fake_get)
    lat, lon = geocode_location.geocode_location("San Francisco", user_agent="custom-ua")
    assert (lat, lon) == (37.77, -122.42)
    assert captured["headers"]["User-Agent"] == "custom-ua"
    assert captured["params"]["limit"] == 1


def test_geocode_location_uses_default_user_agent(monkeypatch):
    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["headers"] = headers
        return DummyResponse([{"lat": "1.0", "lon": "2.0"}])

    monkeypatch.setattr(geocode_location.requests, "get", fake_get)
    geocode_location.geocode_location("Tokyo")
    assert captured["headers"]["User-Agent"] == GEOCODER_DEFAULT_USER_AGENT


def test_geocode_location_raises_when_not_found(monkeypatch):
    monkeypatch.setattr(geocode_location.requests, "get", lambda *args, **kwargs: DummyResponse([]))
    with pytest.raises(ValueError, match="Location not found"):
        geocode_location.geocode_location("Atlantis")


def test_get_json_retries_then_succeeds(monkeypatch):
    calls = {"count": 0}

    def fake_get(url, headers=None, params=None, timeout=None):
        calls["count"] += 1
        if calls["count"] < 3:
            raise requests.Timeout("slow")
        return DummyResponse({"ok": True})

    monkeypatch.setattr(main.session, "get", fake_get)
    monkeypatch.setattr(main.time, "sleep", lambda seconds: None)
    payload = main.get_json("https://example.com")
    assert payload == {"ok": True}
    assert calls["count"] == 3


def test_fetch_helpers_use_safe_json(monkeypatch):
    def fake_get_json(url, **kwargs):
        if "air-quality" in url:
            return {"current": {"us_aqi": 57}}
        if "uv_index" in url:
            return {"current": {"uv_index": 8.4}}
        return {"properties": {"periods": [{"name": "Tonight", "temperature": 55}]}}

    monkeypatch.setattr(main, "get_json", fake_get_json)
    assert main.fetch_aqi(1, 2) == 57
    assert main.fetch_uv(1, 2) == 8.4
    period = main.fetch_forecast_period("https://forecast")
    assert period["name"] == "Tonight"
    assert period["temperature"] == 55


def test_forecast_digest_builds_six_periods():
    session = Mock()
    session.get.side_effect = [
        DummyResponse({"properties": {"forecast": "https://forecast.example"}}),
        DummyResponse(
            {
                "properties": {
                    "periods": [
                        {
                            "name": f"P{i}",
                            "temperature": 60 + i,
                            "temperatureUnit": "F",
                            "windSpeed": "5 mph",
                            "windDirection": "NW",
                            "shortForecast": "Clear",
                            "detailedForecast": "Clear skies.",
                        }
                        for i in range(8)
                    ]
                }
            }
        ),
    ]

    digest = forecast_digest.get_forecast_digest(1.0, 2.0, session=session)
    assert len(digest) == 6
    assert digest[0]["name"] == "P0"
    assert digest[-1]["name"] == "P5"


def test_create_weather_panel_contains_location_title():
    panel = main.create_weather_panel(
        {
            "Timestamp": "2026-06-20 15:00:00",
            "Period": "Afternoon",
            "Forecast": "Sunny",
            "Temperature": "70°F",
            "Wind": "5 mph NW",
            "UV_Index": 7,
            "AQI": 42,
            "AQI_Category_Rich": "[green]Good[/green]",
        },
        "San Francisco",
    )
    assert "San Francisco" in str(panel.title)


def test_run_digest_exits_cleanly(monkeypatch):
    monkeypatch.setattr(
        main.argparse.ArgumentParser,
        "parse_args",
        lambda self: type(
            "Args",
            (),
            {
                "location": "San Francisco, CA",
                "digest": True,
                "watch": False,
                "sleep_minutes": 30,
                "geocoder_user_agent": "student-app/1.0",
            },
        )(),
    )
    monkeypatch.setattr(main, "build_location_context", lambda loc, ua: main.LocationContext(loc, 37.77, -122.42))
    monkeypatch.setattr(main, "get_forecast_digest", lambda lat, lon, session=None: [{"name": "Now", "temperature": 68, "temp_unit": "F", "wind": "5 mph NW", "short_forecast": "Sunny"}])
    printed = []
    monkeypatch.setattr(main.console, "print", lambda *args, **kwargs: printed.append(args))
    with pytest.raises(SystemExit) as exc:
        main.run()
    assert exc.value.code == 0
    assert printed


def test_run_writes_csv_with_partial_api_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(main.argparse.ArgumentParser, "parse_args", lambda self: type("Args", (), {
        "location": "San Francisco, CA",
        "digest": False,
        "watch": False,
        "sleep_minutes": 1,
        "geocoder_user_agent": "student-app/1.0",
    })())
    monkeypatch.setattr(main, "build_location_context", lambda loc, ua: main.LocationContext(loc, 37.77, -122.42))

    def fake_get_json(url, **kwargs):
        if "points" in url:
            return {"properties": {"forecast": "https://forecast.example"}}
        if url == "https://forecast.example":
            return {"properties": {"periods": [{"name": "Now", "shortForecast": "Sunny", "temperature": 70, "temperatureUnit": "F", "windSpeed": "5 mph", "windDirection": "NW"}]}}
        if "air-quality" in url:
            raise requests.ConnectionError("aqi down")
        if "uv_index" in url:
            return {"current": {"uv_index": 9}}
        raise AssertionError(url)

    monkeypatch.setattr(main, "get_json", fake_get_json)
    monkeypatch.setattr(main.console, "print", lambda *args, **kwargs: None)

    class DummyStatus:
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(main.console, "status", lambda *args, **kwargs: DummyStatus())

    state = {"calls": 0}
    def fake_sleep(seconds):
        state["calls"] += 1
        raise KeyboardInterrupt

    monkeypatch.setattr(main.time, "sleep", fake_sleep)
    monkeypatch.setattr(main, "CSV_FILE", str(tmp_path / "weather_log.csv"))
    main.run()

    with open(tmp_path / "weather_log.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert rows[0]["Location"] == "San Francisco, CA"
    assert rows[0]["AQI"] == "N/A"
    assert rows[0]["AQI_Category"] == "N/A"
    assert rows[0]["UV_Index"] == "9"
    assert rows[0]["Forecast"] == "Sunny"
