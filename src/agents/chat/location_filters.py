"""LocationFilters model for resolving location preferences into geographic scopes."""

from typing import Literal

from pydantic import BaseModel, field_validator

from src.core.region.constants import ALL_STATES, REGIONS


class LocationFilters(BaseModel):
    """Resolved location filters from client's raw location preference text.

    Validators silently drop invalid values rather than raising, for defensive
    LLM-extraction handling.
    """

    scope: Literal["nationwide", "region", "states", "metros"]
    region_name: str | None = None  # One of REGIONS keys
    state_names: list[str] = []
    cbsa_names: list[str] = []
    area_type: Literal["urban", "suburban", "rural", "any"] = "any"
    reasoning: str = ""

    @field_validator("region_name", mode="before")
    @classmethod
    def validate_region(cls, v: str | None) -> str | None:
        """Silently drop invalid region names."""
        if v is None or v in REGIONS:
            return v
        return None

    @field_validator("state_names", mode="before")
    @classmethod
    def validate_states(cls, v: list[str]) -> list[str]:
        """Silently filter invalid state names."""
        if not isinstance(v, list):
            return []
        return [s for s in v if s in ALL_STATES]
