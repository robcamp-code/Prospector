"""Location filter extraction for geographic targeting."""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from src.core.region import ALL_STATES, REGIONS


class LocationFilters(BaseModel):
    """Structured location filters extracted from free-form location preferences.

    Used to convert user descriptions like "NYC, LA, Miami" or "Texas and California"
    into valid geographic parameters for database queries.
    """

    scope: Literal["nationwide", "region", "states", "metros"] = Field(
        description="Geographic scope level: nationwide (all US), region (e.g., east_coast), "
        "states (specific states), or metros (specific metro areas/CBSAs)"
    )
    region_name: str | None = Field(
        default=None,
        description="Region name when scope='region'. Must be one of: "
        "east_coast, west_coast, midwest, south, mountain_west",
    )
    state_names: list[str] = Field(
        default_factory=list,
        description="List of full state names when scope='states'. "
        "E.g., ['Texas', 'California']",
    )
    cbsa_names: list[str] = Field(
        default_factory=list,
        description="List of metro area names when scope='metros'. "
        "E.g., ['New York', 'Los Angeles', 'Miami']",
    )
    area_type: Literal["urban", "suburban", "rural", "any"] = Field(
        default="any",
        description="Type of area preference. Currently informational only.",
    )
    reasoning: str = Field(
        description="Brief explanation of why these filters were extracted from the input"
    )

    @field_validator("region_name")
    @classmethod
    def validate_region_name(cls, v: str | None) -> str | None:
        """Validate region_name is a valid region key."""
        if v is None:
            return v
        valid_regions = set(REGIONS.keys())
        if v not in valid_regions:
            return None
        return v

    @field_validator("state_names")
    @classmethod
    def validate_state_names(cls, v: list[str]) -> list[str]:
        """Filter state_names to only include valid US state names."""
        valid_states = set(ALL_STATES)
        return [s for s in v if s in valid_states]
