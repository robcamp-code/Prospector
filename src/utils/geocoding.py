"""Geocoding utilities."""

from geopy.geocoders import Nominatim


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
    geolocator = Nominatim(user_agent="prospector_app")
    location = geolocator.geocode(address)
    if not location:
        raise ValueError(f"Could not geocode: {address}")
    return f"@{location.latitude},{location.longitude},{zoom}z"
