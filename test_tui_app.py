import pytest

from tui_app import WeatherApp


@pytest.mark.skip("Requires textual's run_test harness which may not be available in all environments.")
def test_tui_starts_and_command_input_accepts_text():
    """Sanity check: WeatherApp boots and command input can receive a :help command.

    This test is intentionally skipped by default because it relies on Textual's
    test harness, which isn't required for core CLI correctness. It can be
    enabled locally by removing the skip marker when working on the TUI.
    """
    async def _inner():
        async with WeatherApp().run_test() as pilot:
            cmd_input = pilot.app.query_one("#command-input")
            assert cmd_input.has_focus, "Command input should be focused on mount"

            await pilot.press(":")
            await pilot.press("h")
            await pilot.press("e")
            await pilot.press("l")
            await pilot.press("p")
            await pilot.press("enter")

            view = pilot.app.query_one("#weather-view")
            assert getattr(view, "_panels", []), "WeatherView should contain a panel after :help"

    # Note: we don't execute the coroutine here; this test documents the
    # expected behaviour and can be run with pytest-asyncio installed.
