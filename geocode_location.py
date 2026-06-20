import requests

def geocode_location(query: str, *, timeout=20):
    """
    query: e.g. 'Nob Hill, San Francisco, CA' or '1600 Amphitheatre Pkwy, Mountain View, CA'
    returns: (lat, lon) as floats
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "json", "limit": 1}

    headers = {
        "User-Agent": "WeatherLogger/1.0 (mokubo3@mail.ccsf.edu)"
    }

    res = requests.get(url, params=params, headers=headers, timeout=timeout)
    res.raise_for_status()
    items = res.json()
    if not items:
        raise ValueError(f"Could not geocode: {query!r}")

    return float(items[0]["lat"]), float(items[0]["lon"])