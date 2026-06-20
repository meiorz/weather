import time, csv, os, requests
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
from geocode_location import geocode_location


loc = input("Enter your location: ")
LAT, LON = geocode_location(loc)
print(LAT, LON)

location_name = loc  # whatever the user typed (or you can prompt a cleaner display name)

CSV_FILE = "weather_log.csv"
HEADERS = {"User-Agent": "PythonWeatherScript/2.0", "Accept": "application/geo+json"}

console = Console()

def get_aqi_category_plain(aqi):
    aqi = float(aqi)
    if aqi <= 50: return "Good"
    if aqi <= 100: return "Moderate"
    if aqi <= 150: return "Unhealthy for Sensitive Groups"
    if aqi <= 200: return "Unhealthy"
    if aqi <= 300: return "Very Unhealthy"
    return "Hazardous"

def get_aqi_category_rich(aqi):
    aqi = float(aqi)
    if aqi <= 50: return "[green]Good[/green]"
    if aqi <= 100: return "[yellow]Moderate[/yellow]"
    if aqi <= 150: return "[dark_orange]Unhealthy for Sensitive Groups[/dark_orange]"
    if aqi <= 200: return "[red]Unhealthy[/red]"
    if aqi <= 300: return "[purple]Very Unhealthy[/purple]"
    return "[blink red]Hazardous[/blink red]"

def create_weather_panel(data):
    table = Table(show_header=False, box=box.SIMPLE)
    table.add_column("Metric", style="dim", width=15)
    table.add_column("Value", style="bold white")
    table.add_row("Period", data["Period"])
    table.add_row("Forecast", data["Forecast"])
    table.add_row("Temperature", f"[green]{data['Temperature']}[/green]")
    table.add_row("Wind", data["Wind"])
    table.add_row("UV Index", f"[magenta]{data['UV_Index']}[/magenta]")
    table.add_row("Air Quality", f"{data['AQI']} US AQI ({data['AQI_Category']})")

    return Panel(
    table,
    title=f"[bold cyan]{location_name}[/bold cyan] | {data['Timestamp']}",
    border_style="cyan",
    expand=False,
)


def safe_get(d, *keys, default="N/A"):
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur:
            return default
        cur = cur[k]
    return cur

session = requests.Session()
timeout = 60

def get_json(url, *, headers=None, params=None, timeout=60, retries=3):
    for attempt in range(retries):
        try:
            r = session.get(url, headers=headers, params=params, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)  # 1s, 2s, 4s

console.print(f"[bold cyan]Initializing connections for {location_name} ({LAT}, {LON})...[/bold cyan]")

try:
    points_url = f"https://api.weather.gov/points/{LAT},{LON}"
    points_json = get_json(points_url, headers=HEADERS, timeout=timeout)
    forecast_url = points_json["properties"]["forecast"]

    fieldnames = ["Timestamp","Location","Period","Forecast","Temperature","Wind","UV_Index","AQI","AQI_Category"]

    console.print(f"[bold green]Grid endpoints retrieved.[/bold green] Logging to [italic]{CSV_FILE}[/italic]. Press Ctrl+C to exit.\n")

    while True:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        forecast_res = session.get(forecast_url, headers=HEADERS, timeout=timeout)
        forecast_res.raise_for_status()
        forecast_json = get_json(forecast_url, headers=HEADERS)

        period = safe_get(forecast_json, "properties", "periods", default={})
        # if periods is a list, this may need adjustment; keeping your original intent:
        # period = forecast_json['properties']['periods'][0]
        period = forecast_json["properties"]["periods"][0]

        temp = period.get("temperature", "N/A")
        temp_unit = period.get("temperatureUnit", "F")
        wind_speed = period.get("windSpeed")
        wind_dir = period.get("windDirection")
        wind = "N/A" if wind_speed is None and wind_dir is None else f"{wind_speed} {wind_dir}".strip()

        aq_url = f"https://air-quality-api.open-meteo.com/v1/air-quality?latitude={LAT}&longitude={LON}&current=us_aqi"
        aq_res = session.get(aq_url, timeout=timeout)
        aq_res.raise_for_status()
        aqi = aq_res.json().get("current", {}).get("us_aqi", "N/A")

        uv_url = f"https://api.open-meteo.com/v1/forecast?latitude={LAT}&longitude={LON}&current=uv_index"
        uv_res = session.get(uv_url, timeout=timeout)
        uv_res.raise_for_status()
        uv = uv_res.json().get("current", {}).get("uv_index", "N/A")

        plain_cat = get_aqi_category_plain(aqi) if aqi != "N/A" else "N/A"

        data = {
            "Timestamp": timestamp,
            "Location": location_name,
            "Period": period.get("name", "N/A"),
            "Forecast": period.get("shortForecast", "N/A"),
            "Temperature": f"{temp}°{temp_unit}",
            "Wind": wind,
            "UV_Index": uv,
            "AQI": aqi,
            "AQI_Category": get_aqi_category_rich(aqi) if aqi != "N/A" else "N/A",
        }

        console.print(create_weather_panel(data))

        file_exists = os.path.isfile(CSV_FILE)
        csv_row = dict(data)
        csv_row["AQI_Category"] = plain_cat

        with open(CSV_FILE, mode="a", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(csv_row)

        sleep_minutes = 30
        with console.status(f"[bold dark_gray]Sleeping for {sleep_minutes} minutes... Next fetch scheduled.[/bold dark_gray]", spinner="dots"):
            time.sleep(sleep_minutes * 60)

except KeyboardInterrupt:
    console.print("\n[bold red]Script terminated by user.[/bold red]")
except requests.RequestException as e:
    console.print(f"\n[bold red]Network/API error:[/bold red] {e}")
except Exception as e:
    console.print(f"\n[bold red]An error occurred:[/bold red] {e}")
