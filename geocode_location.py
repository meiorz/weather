import requests

from config import GEOCODER_DEFAULT_USER_AGENT


def geocode_location(query: str, *, user_agent: str | None = None, timeout: int = 20) -> tuple[float, float]:
    """
    query: e.g. 'Nob Hill, San Francisco, CA' or '1600 Amphitheatre Pkwy, Mountain View, CA'
    user_agent: caller-provided identifier for Nominatim requests
    returns: (lat, lon) as floats
    """
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "json", "limit": 1}
    headers = {"User-Agent": user_agent or GEOCODER_DEFAULT_USER_AGENT}

    res = requests.get(url, params=params, headers=headers, timeout=timeout)
    res.raise_for_status()
    data = res.json()
    if not data:
        raise ValueError(f"Location not found: {query}")

    return float(data[0]["lat"]), float(data[0]["lon"])
