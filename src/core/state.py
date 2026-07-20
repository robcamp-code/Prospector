"""Shared state models for cross-agent use."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DemographicTargetRef(BaseModel):
    """Serializable demographic target for LangGraph state."""

    demographic_key: str
    constraint_type: Literal["range", "threshold_min", "threshold_max", "percentage"]
    min_value: float | None = None
    max_value: float | None = None
    target_percentage: float | None = None
    percentage_operator: Literal["gt", "lt", "gte", "lte", "eq"] | None = None
    importance_weight: float = Field(default=0.5, ge=0, le=1)


# Pydantic models for structured data within state
class ClientProfileRef(BaseModel):
    """Serializable profile reference for LangGraph state."""

    profile_id: str | None = None  # None before saved to DB
    name: str | None = None
    business_type: str | None = None
    service_description: str | None = None
    competitor_types: list[str] = Field(default_factory=list)
    complimentary_types: list[str] = Field(default_factory=list)
    target_income_min: int | None = None
    target_income_max: int | None = None
    target_demographics: list[DemographicTargetRef] = Field(default_factory=list)
