"""Strictly-typed client preferences: the single source of truth the agent
extracts, persists on ClientProfile, and turns into aggregation queries.

Location fields map 1:1 onto the aggregation service's WHERE-clause filters;
they never influence GROUP BY. Types derive from the region constants and the
demographic catalog so LLM structured output cannot emit unknown values.
"""

from typing import Literal, get_args

from pydantic import BaseModel, Field, field_validator

from src.core.demographics import CategoryName
from src.core.region.constants import ALL_STATES, REGIONS
from src.core.urbanicity import density_bounds

# Literal of REGIONS keys, asserted in tests to stay in sync with constants.
RegionName = Literal["east_coast", "west_coast", "midwest", "south", "mountain_west"]
AreaType = Literal["urban", "suburban", "rural", "any"]


class LocationPreference(BaseModel):
    """Where the client wants to operate. All fields optional; empty = nationwide.

    Every field is a WHERE-clause filter for the aggregation service.
    """

    region: RegionName | None = None
    states: list[str] = Field(default_factory=list)
    cbsa: str | None = None
    city: str | None = None
    area_type: AreaType = "any"

    @field_validator("states", mode="before")
    @classmethod
    def validate_states(cls, v: list[str]) -> list[str]:
        """Silently drop unknown state names (defensive LLM-extraction handling)."""
        if not isinstance(v, list):
            return []
        return [s for s in v if s in ALL_STATES]

    def is_nationwide(self) -> bool:
        return not (self.region or self.states or self.cbsa or self.city)

    def filter_kwargs(self) -> dict:
        """Map to get_aggregation WHERE-filter kwargs (region/states/cbsa/city/density)."""
        min_density, max_density = density_bounds(self.area_type)
        return {
            "region": self.region,
            "states": self.states or None,
            "cbsa": self.cbsa,
            "city": self.city,
            "min_density": min_density,
            "max_density": max_density,
        }

    def describe(self) -> str:
        """Human-readable scope, e.g. 'east_coast, urban areas' or 'nationwide'."""
        parts = []
        if self.region:
            parts.append(self.region)
        if self.states:
            parts.append(", ".join(self.states))
        if self.cbsa:
            parts.append(self.cbsa)
        if self.city:
            parts.append(self.city)
        scope = " / ".join(parts) if parts else "nationwide"
        if self.area_type != "any":
            scope += f", {self.area_type} areas"
        return scope


class Preferences(BaseModel):
    """Everything the Profile Builder must learn before a report can be built."""

    name: str | None = None
    business_type: str | None = None
    service_description: str | None = None
    price_point: str | None = None
    target_customer_description: str | None = None
    location: LocationPreference | None = None
    demographic_categories: list[CategoryName] = Field(default_factory=list)

    def _required(self) -> list[tuple[str, object]]:
        return [
            ("name", self.name),
            ("business_type", self.business_type),
            ("service_description", self.service_description),
            ("price_point", self.price_point),
            ("target_customer_description", self.target_customer_description),
            ("location", self.location),
            ("demographic_categories", self.demographic_categories),
        ]

    def is_complete(self) -> bool:
        return not self.missing_fields()

    def missing_fields(self) -> list[str]:
        missing = []
        for field_name, value in self._required():
            if isinstance(value, str):
                if not value.strip():
                    missing.append(field_name)
            elif not value:
                missing.append(field_name)
        return missing

    def merge_missing_from(self, other: "Preferences") -> "Preferences":
        """Fill any empty field from an earlier extraction (new values win)."""
        update = {}
        for field_name in type(self).model_fields:
            if not getattr(self, field_name) and getattr(other, field_name):
                update[field_name] = getattr(other, field_name)
        return self.model_copy(update=update)


def load_preferences(raw: dict | None) -> Preferences | None:
    """Safely revalidate persisted/checkpointed preferences.

    Returns None on schema drift or corrupt data so a resumed conversation
    re-extracts instead of crashing the thread.
    """
    if not isinstance(raw, dict):
        return None
    try:
        return Preferences.model_validate(raw)
    except Exception:
        return None


def _assert_literals_in_sync() -> None:
    # RegionName must mirror REGIONS keys; fail fast at import if they drift.
    assert set(get_args(RegionName)) == set(REGIONS), (
        "RegionName Literal out of sync with REGIONS keys"
    )


_assert_literals_in_sync()
