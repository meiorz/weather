from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from rich.console import RenderableType
from rich.panel import Panel

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Static, Input
from textual.timer import Timer

from config import HEADERS
from main import (
    LocationContext,
    build_location_context,
    create_weather_panel,
    create_digest_panel,
    fetch_aqi,
    fetch_uv,
    fetch_forecast_period,
    get_json,
)


@dataclass
class AppState:
    location: str = "San Francisco, CA"
    interval_minutes: int = 30
    status: str = "RUNNING"  # RUNNING | PAUSED | ERROR
    last_update: Optional[datetime] = None
    last_error: Optional[str] = None


class CommandEntered(Message):
    def __init__(self, command: str) -> None:
        self.command = command
        super().__init__()


class NewWeatherPanel(Message):
    def __init__(self, panel: RenderableType) -> None:
        self.panel = panel
        super().__init__()


class HeaderBar(Static):
    app_state: AppState = reactive(AppState(), layout=True)

    def update_state(self, state: AppState) -> None:
        self.app_state = state
        self.refresh()

    def render(self) -> RenderableType:
        state = self.app_state
        loc = state.location
        status = state.status
        last = state.last_update.strftime("%H:%M:%S") if state.last_update else "—"
        interval = state.interval_minutes
        text = (
            f"[bold cyan]weather[/bold cyan] · {loc} "
            f"· status: [bold]{status}[/bold] "
            f"· last: {last} · interval: {interval}m"
        )
        if state.last_error:
            text += f" · [red]{state.last_error}[/red]"
        return text


class WeatherView(Static):
    def on_mount(self) -> None:
        self._panels: list[RenderableType] = []
        self.update("")

    def push_panel(self, panel: RenderableType) -> None:
        self._panels.append(panel)
        self._panels = self._panels[-40:]
        self.update(Vertical(*self._panels))
        self.scroll_end(animate=False)

    def clear(self) -> None:
        self._panels.clear()
        self.update("")


class Sidebar(Static):
    def update_summary(self, *, aqi: str = "N/A", uv: str = "N/A") -> None:
        panel = Panel.fit(
            f"[bold]Summary[/bold]\n\nAQI: {aqi}\nUV Index: {uv}",
            title="Status",
            border_style="cyan",
        )
        self.update(panel)


class CommandBar(Static):
    def on_mount(self) -> None:
        self.update(
            ":help · :loc <place> · :interval <min> · :pause · :resume · :digest · :clear · :q"
        )


class CommandInput(Input):
    def on_mount(self) -> None:
        self.placeholder = "Type a command (e.g., :loc San Francisco, CA) and press Enter"
        self.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        if cmd:
            self.post_message(CommandEntered(cmd))
        self.value = ""


class WeatherApp(App):
    """Claude Code–style TUI shell for the weather CLI using Textual."""

    CSS = """
    Screen { layout: vertical; }
    #header { height: 1; }
    #main-row { height: 1fr; }
    #weather-view { width: 3fr; }
    #sidebar { width: 1fr; }
    #command-bar { height: 1; }
    #command-input { height: 1; }
    """

    BINDINGS = [
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.state = AppState()
        self._poll_timer: Optional[Timer] = None
        self._location_ctx: Optional[LocationContext] = None
        self._forecast_url: Optional[str] = None

    def compose(self) -> ComposeResult:
        yield HeaderBar(id="header")
        with Horizontal(id="main-row"):
            yield WeatherView(id="weather-view")
            yield Sidebar(id="sidebar")
        yield CommandBar(id="command-bar")
        yield CommandInput(id="command-input")

    async def on_mount(self) -> None:
        await self._set_location(self.state.location)
        self._start_polling_timer()

    def _start_polling_timer(self) -> None:
        if self._poll_timer is not None:
            self._poll_timer.stop()
        seconds = self.state.interval_minutes * 60
        self._poll_timer = self.set_interval(
            seconds,
            self._tick_weather,
            pause=(self.state.status != "RUNNING"),
        )

    def _pause_polling(self) -> None:
        if self._poll_timer is not None:
            self._poll_timer.pause()

    def _resume_polling(self) -> None:
        if self._poll_timer is not None:
            self._poll_timer.resume()

    async def _set_location(self, location_str: str) -> None:
        header = self.query_one(HeaderBar)
        view = self.query_one(WeatherView)

        try:
            ctx = build_location_context(location_str, user_agent="weather-tui/1.0")
            self._location_ctx = ctx
            self.state.location = ctx.name
            self.state.last_error = None

            points_url = f"https://api.weather.gov/points/{ctx.lat},{ctx.lon}"
            points_json = get_json(points_url, headers=HEADERS)
            self._forecast_url = points_json["properties"]["forecast"]

            view.push_panel(Panel(f"Location set to [bold]{ctx.name}[/bold].", border_style="green"))
        except Exception as e:
            self.state.last_error = f"Location error: {e}"
            view.push_panel(Panel(str(e), border_style="red"))
        finally:
            header.update_state(self.state)

    async def _tick_weather(self) -> None:
        if self.state.status != "RUNNING":
            return
        if not self._location_ctx or not self._forecast_url:
            return

        header = self.query_one(HeaderBar)
        view = self.query_one(WeatherView)
        sidebar = self.query_one(Sidebar)

        ctx = self._location_ctx

        try:
            period = fetch_forecast_period(self._forecast_url)
        except Exception as e:
            self.state.last_error = f"Forecast fetch failed: {e}"
            header.update_state(self.state)
            view.push_panel(Panel(f"[red]Forecast fetch failed:[/red] {e}", border_style="red"))
            return

        try:
            aqi = fetch_aqi(ctx.lat, ctx.lon)
        except Exception as e:
            aqi = "N/A"
            view.push_panel(Panel(f"[red]AQI fetch failed:[/red] {e}", border_style="red"))

        try:
            uv = fetch_uv(ctx.lat, ctx.lon)
        except Exception as e:
            uv = "N/A"
            view.push_panel(Panel(f"[red]UV fetch failed:[/red] {e}", border_style="red"))

        self.state.last_update = datetime.now()
        self.state.last_error = None
        header.update_state(self.state)

        data = {
            "Timestamp": self.state.last_update.strftime("%Y-%m-%d %H:%M:%S"),
            "Location": ctx.name,
            "Period": period.get("name", "N/A"),
            "Forecast": period.get("shortForecast", "N/A"),
            "Temperature": f"{period.get('temperature', 'N/A')}°{period.get('temperatureUnit', 'F')}",
            "Wind": " ".join(
                x
                for x in [period.get("windSpeed"), period.get("windDirection")]
                if x is not None
            )
            or "N/A",
            "UV_Index": uv,
            "AQI": aqi,
            "AQI_Category": "N/A",
            "AQI_Category_Rich": "N/A",
        }
        panel = create_weather_panel(data, ctx.name)
        view.push_panel(panel)

        sidebar.update_summary(aqi=str(aqi), uv=str(uv))

    def on_new_weather_panel(self, message: NewWeatherPanel) -> None:
        self.query_one(WeatherView).push_panel(message.panel)

    async def on_command_entered(self, message: CommandEntered) -> None:
        await self._handle_command(message.command)

    async def _handle_command(self, raw: str) -> None:
        view = self.query_one(WeatherView)
        header = self.query_one(HeaderBar)
        sidebar = self.query_one(Sidebar)

        def set_error(msg: str) -> None:
            self.state.last_error = msg or None
            header.update_state(self.state)

        view.push_panel(Panel(f"[bold magenta]Command>[/bold magenta] {raw}", border_style="magenta"))

        if raw in (":q", "exit", ":quit"):
            self.exit()
            return

        if raw == ":help":
            view.push_panel(
                Panel(
                    ":help · :loc <place> · :interval <min> · :pause · :resume · :digest · :clear · :q",
                    title="Help",
                    border_style="green",
                )
            )
            set_error("")
            return

        if raw == ":clear":
            view.clear()
            set_error("")
            return

        if raw.startswith(":loc "):
            loc = raw[5:].strip()
            if not loc:
                set_error("Location cannot be empty.")
                return
            await self._set_location(loc)
            await self._tick_weather()
            return

        if raw.startswith(":interval "):
            arg = raw[len(":interval ") :].strip()
            try:
                minutes = int(arg)
                if minutes <= 0:
                    raise ValueError
            except ValueError:
                set_error("Interval must be a positive integer (minutes).")
                return
            self.state.interval_minutes = minutes
            set_error("")
            header.update_state(self.state)
            self._start_polling_timer()
            view.push_panel(Panel(f"Interval set to {minutes} minute(s).", border_style="green"))
            return

        if raw == ":pause":
            if self.state.status == "PAUSED":
                set_error("Already paused.")
                return
            self.state.status = "PAUSED"
            self._pause_polling()
            set_error("")
            header.update_state(self.state)
            view.push_panel(Panel("Polling [bold yellow]paused[/bold yellow].", border_style="yellow"))
            return

        if raw == ":resume":
            if self.state.status == "RUNNING":
                set_error("Already running.")
                return
            self.state.status = "RUNNING"
            self._resume_polling()
            set_error("")
            header.update_state(self.state)
            view.push_panel(Panel("Polling [bold green]resumed[/bold green].", border_style="green"))
            return

        if raw == ":digest":
            try:
                ctx = self._location_ctx
                if ctx is None:
                    raise RuntimeError("No location set yet.")
                from forecast_digest import get_forecast_digest

                digest = get_forecast_digest(ctx.lat, ctx.lon)
                digest_panel = create_digest_panel(digest, ctx.name)
                view.push_panel(digest_panel)
                set_error("")
            except Exception as e:
                set_error(f"Digest error: {e}")
                view.push_panel(Panel(str(e), border_style="red"))
            return

        set_error(f"Unknown command: {raw!r}")

    def action_quit(self) -> None:
        self.exit()


if __name__ == "__main__":
    WeatherApp().run()
