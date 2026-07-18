"""Geocoding utilities."""

from geopy.geocoders import Nominatim


_geolocator = Nominatim(user_agent="prospector_app")


def geocode(address: str) -> tuple[float, float]:
    """
    Convert an address to latitude/longitude coordinates.

    Args:
        address: The address to geocode (e.g., "123 Main St, Phoenix, AZ")

    Returns:
        A tuple of (latitude, longitude)

    Raises:
        ValueError: If the address cannot be geocoded
    """
    location = _geolocator.geocode(address)
    if not location:
        raise ValueError(f"Could not geocode: {address}")
    return (location.latitude, location.longitude)


def to_ll(address: str, zoom: int = 14) -> str:
    """
    Convert an address to a latitude/longitude string for SerpAPI.

    Args:
        address: The address to geocode (e.g., "Atlanta, GA")
        zoom: Zoom level for the map (default 14)

    Returns:
        A string in format "@latitude,longitude,zoomz" for SerpAPI Google Maps searches

    Raises:
        ValueError: If the address cannot be geocoded
    """
    lat, lng = geocode(address)
    return f"@{lat},{lng},{zoom}z"
