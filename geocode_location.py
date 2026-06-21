import requests


def geocode_location(query: str, email: str, *, timeout: int = 20) -> tuple[float, float]:
    """
    query: e.g. 'Nob Hill, San Francisco, CA' or '1600 Amphitheatre Pkwy, Mountain View, CA'
    email: user email for the User-Agent header (Nominatim requires this)
    returns: (lat, lon) as floats
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "json", "limit": 1}
    headers = {
        "User-Agent": f"WeatherLogger/1.0 ({email})"
    }

    res = requests.get(url, params=params, headers=headers, timeout=timeout)
    res.raise_for_status()
    items = res.json()
    if not items:
        raise ValueError(f"Could not geocode: {query!r}")

    return float(items[0]["lat"]), float(items[0]["lon"])
