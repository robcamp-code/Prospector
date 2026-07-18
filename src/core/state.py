"""Shared state models for cross-agent use."""

from typing import Annotated

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


# Pydantic models for structured data within state
class ClientProfileRef(BaseModel):
    """Serializable profile reference for LangGraph state."""

    profile_id: int
    name: str
    business_type: str | None = None
    competitor_types: list[str] = Field(default_factory=list)
    complimentary_types: list[str] = Field(default_factory=list)
    target_income_min: int | None = None
    target_income_max: int | None = None


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
