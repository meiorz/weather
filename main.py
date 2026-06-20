import time
import csv
import os
import requests
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from geocode_location import geocode_location

loc = input("Enter your location: ")
LAT, LON = geocode_location(loc)

location_name = loc

CSV_FILE = "weather_log.csv"
HEADERS = {"User-Agent": "PythonWeatherScript/2.0", "Accept": "application/geo+json"}

console = Console()


def get_aqi_category(aqi, *, rich: bool = False) -> str:
    """Return AQI category string. Pass rich=True for Rich markup color tags."""
    aqi = float(aqi)
    levels = [
        (50,  "Good",                              "[green]",       "[/green]"),
        (100, "Moderate",                          "[yellow]",      "[/yellow]"),
        (150, "Unhealthy for Sensitive Groups",    "[dark_orange]", "[/dark_orange]"),
        (200, "Unhealthy",                         "[red]",         "[/red]"),
        (300, "Very Unhealthy",                    "[purple]",      "[/purple]"),
    ]
    for threshold, label, open_tag, close_tag in levels:
        if aqi <= threshold:
            return f"{open_tag}{label}{close_tag}" if rich else label
    return "[blink red]Hazardous[/blink red]" if rich else "Hazardous"


def create_weather_panel(data: dict) -> Panel:
    table = Table(show_header=False, box=box.SIMPLE)
    table.add_column("Metric", style="dim", width=15)
    table.add_column("Value", style="bold white")
    table.add_row("Period",      data["Period"])
    table.add_row("Forecast",    data["Forecast"])
    table.add_row("Temperature", f"[green]{data['Temperature']}[/green]")
    table.add_row("Wind",        data["Wind"])
    table.add_row("UV Index",    f"[magenta]{data['UV_Index']}[/magenta]")
    table.add_row("Air Quality", f"{data['AQI']} US AQI ({data['AQI_Category_Rich']})")

    return Panel(
        table,
        title=f"[bold cyan]{location_name}[/bold cyan] | {data['Timestamp']}",
        border_style="cyan",
        expand=False,
    )


def safe_get(d: dict, *keys, default="N/A"):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur


session = requests.Session()
TIMEOUT = 60


def get_json(url: str, *, headers=None, params=None, timeout: int = TIMEOUT, retries: int = 3):
    for attempt in range(retries):
        try:
            r = session.get(url, headers=headers, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except (requests.Timeout, requests.ConnectionError):
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)  # 1s, 2s, 4s


console.print(f"[bold cyan]Initializing connections for {location_name} ({LAT}, {LON})...[/bold cyan]")

try:
    points_url = f"https://api.weather.gov/points/{LAT},{LON}"
    points_json = get_json(points_url, headers=HEADERS)
    forecast_url = points_json["properties"]["forecast"]

    fieldnames = ["Timestamp", "Location", "Period", "Forecast",
                  "Temperature", "Wind", "UV_Index", "AQI", "AQI_Category"]

    console.print(
        f"[bold green]Grid endpoints retrieved.[/bold green] "
        f"Logging to [italic]{CSV_FILE}[/italic]. Press Ctrl+C to exit.\n"
    )

    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        forecast_json = get_json(forecast_url, headers=HEADERS)
        period = forecast_json["properties"]["periods"][0]

        temp      = period.get("temperature", "N/A")
        temp_unit = period.get("temperatureUnit", "F")
        wind_speed = period.get("windSpeed")
        wind_dir   = period.get("windDirection")
        wind = "N/A" if (wind_speed is None and wind_dir is None) else f"{wind_speed} {wind_dir}".strip()

        aq_url  = (f"https://air-quality-api.open-meteo.com/v1/air-quality"
                   f"?latitude={LAT}&longitude={LON}&current=us_aqi")
        aqi = get_json(aq_url, timeout=TIMEOUT).get("current", {}).get("us_aqi", "N/A")

        uv_url = (f"https://api.open-meteo.com/v1/forecast"
                  f"?latitude={LAT}&longitude={LON}&current=uv_index")
        uv = get_json(uv_url, timeout=TIMEOUT).get("current", {}).get("uv_index", "N/A")

        plain_cat = get_aqi_category(aqi) if aqi != "N/A" else "N/A"
        rich_cat  = get_aqi_category(aqi, rich=True) if aqi != "N/A" else "N/A"

        data = {
            "Timestamp":       timestamp,
            "Location":        location_name,
            "Period":          period.get("name", "N/A"),
            "Forecast":        period.get("shortForecast", "N/A"),
            "Temperature":     f"{temp}\u00b0{temp_unit}",
            "Wind":            wind,
            "UV_Index":        uv,
            "AQI":             aqi,
            "AQI_Category":    plain_cat,
            "AQI_Category_Rich": rich_cat,
        }

        console.print(create_weather_panel(data))

        file_exists = os.path.isfile(CSV_FILE)
        csv_row = {k: data[k] for k in fieldnames}

        with open(CSV_FILE, mode="a", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(csv_row)

        sleep_minutes = 30
        with console.status(
            f"[bold dark_gray]Sleeping for {sleep_minutes} minutes... Next fetch scheduled.[/bold dark_gray]",
            spinner="dots",
        ):
            time.sleep(sleep_minutes * 60)

except KeyboardInterrupt:
    console.print("\n[bold red]Script terminated by user.[/bold red]")
except requests.RequestException as e:
    console.print(f"\n[bold red]Network/API error:[/bold red] {e}")
except Exception as e:
    console.print(f"\n[bold red]An error occurred:[/bold red] {e}")
