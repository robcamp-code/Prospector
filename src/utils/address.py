"""Address parsing utilities."""

from dataclasses import dataclass

import usaddress


@dataclass
class ParsedAddress:
    """Parsed address components."""

    street: str | None
    city: str | None
    state: str | None
    zip_code: str | None


# Components that make up the street address
_STREET_COMPONENTS = (
    "AddressNumber",
    "AddressNumberPrefix",
    "AddressNumberSuffix",
    "StreetName",
    "StreetNamePreDirectional",
    "StreetNamePreModifier",
    "StreetNamePreType",
    "StreetNamePostDirectional",
    "StreetNamePostModifier",
    "StreetNamePostType",
    "SubaddressType",
    "SubaddressIdentifier",
    "OccupancyType",
    "OccupancyIdentifier",
)


def parse_address(address: str) -> ParsedAddress:
    """
    Parse an address string into its components.

    Args:
        address: A US address string (e.g., "123 Main St, Atlanta, GA 30301")

    Returns:
        ParsedAddress with street, city, state, and zip_code fields.
        Fields will be None if they cannot be extracted.

    Example:
        >>> result = parse_address("123 Main St, Atlanta, GA 30301")
        >>> result.street
        '123 Main St'
        >>> result.city
        'Atlanta'
        >>> result.state
        'GA'
        >>> result.zip_code
        '30301'
    """
    try:
        parsed = usaddress.parse(address)
    except Exception:
        return ParsedAddress(street=None, city=None, state=None, zip_code=None)

    # Build street address preserving original token order
    street_parts = []
    city = None
    state = None
    zip_code = None

    for value, label in parsed:
        # Strip trailing punctuation
        clean_value = value.rstrip(",;")
        if label in _STREET_COMPONENTS:
            street_parts.append(clean_value)
        elif label == "PlaceName":
            city = f"{city} {clean_value}".strip() if city else clean_value
        elif label == "StateName":
            state = clean_value
        elif label == "ZipCode":
            zip_code = clean_value

    street = " ".join(street_parts) if street_parts else None

    return ParsedAddress(street=street, city=city, state=state, zip_code=zip_code)
