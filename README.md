# Weather Dashboard

A terminal-based Python CLI that fetches real-time **NOAA weather**, **UV Index**, and **Air Quality Index** for any location, with a Rich UI and CSV logging.

![Demo](demo.gif)

## Features

- Real-time weather from NOAA (temperature, wind, forecast)
- UV Index via Open-Meteo
- Air Quality Index (US AQI) via Open-Meteo with color-coded categories
- 6-period forecast digest (next ~3 days at a glance)
- CSV logging for historical data
- Retry logic with exponential backoff on network errors

## Installation

```bash
pip install -r requirements.txt
```

## Usage

```bash
# Interactive live loop — prompts for location, refreshes every 30 min
python main.py

# Live loop with location flag (no prompt)
python main.py -l "San Francisco, CA"

# One-shot 6-period forecast digest
python main.py --digest -l "San Francisco, CA"

# Digest that refreshes every 6 hours
python main.py --digest --watch -l "San Francisco, CA"
```

## CLI Flags

| Flag | Short | Description |
|---|---|---|
| `--location` | `-l` | Location string, skips interactive prompt |
| `--digest` | | Print 6-period forecast digest |
| `--watch` | | Use with `--digest` to refresh every 6 hours |

## Running Tests

```bash
pip install pytest
python -m pytest test_weather.py -v
```

21 tests covering AQI categorization, safe key access, geocoding, HTTP retry logic, and forecast digest normalization.

## Project Structure

```
weather/
├── main.py               # Entry point, Rich UI, live loop
├── forecast_digest.py    # 6-period NOAA forecast fetcher
├── geocode_location.py   # Nominatim geocoding
├── test_weather.py       # Unit tests
├── requirements.txt
└── weather_log.csv       # Auto-generated on first run
```

## Data Sources

- [NOAA Weather API](https://api.weather.gov) — forecast and conditions
- [Open-Meteo](https://open-meteo.com) — UV Index and Air Quality
- [Nominatim / OpenStreetMap](https://nominatim.openstreetmap.org) — geocoding
