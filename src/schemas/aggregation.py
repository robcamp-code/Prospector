"""Aggregation endpoint request and response schemas."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class GeographyLevel(StrEnum):
    """Geography level for grouping in aggregation queries."""

    ZIP = "zip"
    COUNTY = "county"
    STATE = "state"
    CITY = "city"
    CBSA = "cbsa"
    REGION = "region"


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
