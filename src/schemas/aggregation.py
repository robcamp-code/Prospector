"""Aggregation endpoint request and response schemas."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from src.core.demographics import DEMOGRAPHICS


class GeographyLevel(StrEnum):
    """Geography level for grouping in aggregation queries."""

    ZIP = "zip"
    COUNTY = "county"
    STATE = "state"
    CITY = "city"
    CBSA = "cbsa"
    REGION = "region"


class AggregationQuery(BaseModel):
    """A single planned aggregation query: grouping, metrics, sorting only.

    Deliberately has NO location fields — the client's location preference is
    injected as WHERE-clause filters at execution time and is never an LLM
    choice, so a query can't widen or drop the geographic scope.
    """

    group_by: Literal["state", "county", "zip", "city", "cbsa"]
    # May validate to empty if all selectors were invalid; the Data Analyst
    # drops empty queries in code rather than failing the whole plan.
    metrics: list[str] = Field(default_factory=list)
    sort_by: str | None = None
    sort_dir: Literal["asc", "desc"] = "desc"
    limit: int = Field(50, ge=1, le=1000)

    @field_validator("metrics", mode="before")
    @classmethod
    def drop_unknown_metrics(cls, v: list[str]) -> list[str]:
        """Silently drop invalid 'category.metric' selectors (defensive LLM handling)."""
        if not isinstance(v, list):
            return []
        valid = []
        for selector in v:
            if not isinstance(selector, str) or "." not in selector:
                continue
            category, metric = selector.split(".", 1)
            if (
                category in DEMOGRAPHICS.categories
                and metric in DEMOGRAPHICS.get_category(category).metrics
            ):
                valid.append(selector)
        return valid


class QueryPlan(BaseModel):
    """The Data Analyst's output: an ordered list of queries to execute."""

    queries: list[AggregationQuery] = Field(default_factory=list, max_length=6)
    reasoning: str = ""


class AggregationRow(BaseModel):
    """A single aggregated row in an aggregation response."""

    group: dict[str, str]
    population: float
    density: float | None = None
    metrics: dict[str, float | dict[str, float]]


class AggregationResponse(BaseModel):
    """Response for /get-aggregation endpoint."""

    rows: list[AggregationRow]
    limit: int
    offset: int
    total_count: int | None = None
