"""Orchestrator state definition."""

from langgraph.prebuilt.chat_agent_executor import AgentState

from src.v0.agents.sql_analyst.models import AnalysisResult
from src.v0.models.state_models import ClientProfileRef


class ProspectorState(AgentState):
    """Global state for the Prospector orchestrator.

    Extends AgentState which provides:
    - messages: Annotated[list, add_messages]
    - remaining_steps: int (required by create_react_agent)

    This state is shared across all orchestrator interactions and persists
    via LangGraph checkpointing.
    """

    client_profile: ClientProfileRef | None
    current_task: str | None  # e.g., "site_selection", "trade_area"
    target_location: str | None  # User's target geography
    analysis_result: AnalysisResult | None  # Result from SQL Analyst Agent
