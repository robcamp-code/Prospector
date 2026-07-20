"""Shared state models for cross-agent use."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

if TYPE_CHECKING:
    from src.schemas.report import Report


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


# TypedDict required by LangGraph StateGraph
class GlobalState(TypedDict):
    """Shared state for all agents.

    Uses LangGraph's add_messages annotation for automatic message handling.
    Pydantic models can be used as field types for structured data.
    """

    messages: Annotated[list, add_messages]
    client_profile: ClientProfileRef | None
    current_task: str | None
    target_location: str | None
    report: Report | None
