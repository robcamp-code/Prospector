"""Urbanicity classification by population density (people per km²).

Thresholds follow the EU/OECD "Degree of Urbanisation" (DEGURBA) standard:
urban centres >= 1,500/km², urban clusters (suburban) >= 300/km², rural
below 300/km². Units match ``uszips.density`` (people/km²). DEGURBA is
defined on 1 km grid cells; ZIP polygons are coarser, so these cuts are
approximations — tune here if bucket sizes look wrong against real data.
"""

URBAN_MIN_DENSITY: float = 1500.0
SUBURBAN_MIN_DENSITY: float = 300.0

# area_type -> (min_density, max_density); None means unbounded on that side.
DENSITY_BOUNDS: dict[str, tuple[float | None, float | None]] = {
    "urban": (URBAN_MIN_DENSITY, None),
    "suburban": (SUBURBAN_MIN_DENSITY, URBAN_MIN_DENSITY),
    "rural": (None, SUBURBAN_MIN_DENSITY),
    "any": (None, None),
}


def density_bounds(area_type: str) -> tuple[float | None, float | None]:
    """Map an area type (urban/suburban/rural/any) to density WHERE bounds."""
    return DENSITY_BOUNDS.get(area_type, (None, None))
