import pytest

from tui_app import WeatherApp, WeatherView


def _install_fake_backends(monkeypatch):
    """Patch out all network and heavy calls so TUI tests are fast and deterministic."""
    import tui_app

    class DummyCtx:
        def __init__(self):
            self.name = "Test City"
            self.lat = 1.0
            self.lon = 2.0

    def fake_build_location_context(location, user_agent):
        return DummyCtx()

    def fake_get_json(url, headers=None):
        return {"properties": {"forecast": "https://example.com/forecast"}}

    def fake_fetch_forecast_period(url):
        return {
            "name": "Now",
            "shortForecast": "Sunny",
            "temperature": 70,
            "temperatureUnit": "F",
            "windSpeed": "5 mph",
            "windDirection": "NW",
        }

    def fake_fetch_aqi(lat, lon):
        return 42

    def fake_fetch_uv(lat, lon):
        return 7

    def fake_get_forecast_digest(lat, lon):
        return [
            {
                "name": "Now",
                "temperature": 70,
                "temp_unit": "F",
                "wind": "5 mph NW",
                "short_forecast": "Sunny",
                "detailed_forecast": "Clear skies.",
            }
        ]

    # Patch in tui_app module namespace (so run_in_thread calls these)
    monkeypatch.setattr(tui_app, "build_location_context", fake_build_location_context)
    monkeypatch.setattr(tui_app, "get_json", fake_get_json)
    monkeypatch.setattr(tui_app, "fetch_forecast_period", fake_fetch_forecast_period)
    monkeypatch.setattr(tui_app, "fetch_aqi", fake_fetch_aqi)
    monkeypatch.setattr(tui_app, "fetch_uv", fake_fetch_uv)
    monkeypatch.setattr(tui_app, "get_forecast_digest", fake_get_forecast_digest, raising=False)


@pytest.mark.asyncio
async def test_tui_starts_and_focuses_command_input(monkeypatch):
    _install_fake_backends(monkeypatch)

    async with WeatherApp().run_test() as pilot:
        cmd_input = pilot.app.query_one("#command-input")
        assert cmd_input.has_focus, "Command input should be focused on mount"


@pytest.mark.asyncio
async def test_help_command_adds_panel(monkeypatch):
    _install_fake_backends(monkeypatch)

    async with WeatherApp().run_test() as pilot:
        app = pilot.app
        view: WeatherView = app.query_one("#weather-view")
        initial_count = len(getattr(view, "_panels", []))

        await app._handle_command(":help")

        panels = getattr(view, "_panels", [])
        # Panel list should have grown after :help
        assert len(panels) > initial_count


@pytest.mark.asyncio
async def test_interval_pause_resume_update_state(monkeypatch):
    _install_fake_backends(monkeypatch)

    async with WeatherApp().run_test() as pilot:
        app = pilot.app

        # interval
        await app._handle_command(":interval 5")
        assert app.state.interval_minutes == 5

        # pause
        await app._handle_command(":pause")
        assert app.state.status == "PAUSED"

        # resume
        await app._handle_command(":resume")
        assert app.state.status == "RUNNING"
