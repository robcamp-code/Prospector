"""Graph state definition for the multi-node Profile Builder -> Data Analyst -> Report Builder agent."""

from typing import Annotated

from langgraph.graph import add_messages
from typing_extensions import TypedDict

from src.core.state import ClientProfileRef
from src.schemas.report import Report


class AnalysisPlan(TypedDict):
    """Data Analyst's output: the query plan for Report Builder."""

    location: dict  # LocationFilters.model_dump()
    categories: list[str]  # List of CategoryName strings to query
    geography_level: str  # GeographyLevel string (zip/county/state/city/cbsa/region)
    reasoning: str


class GraphState(TypedDict):
    """State shared across all three graph nodes.

    messages: Conversation history (LangChain message objects), using add_messages reducer
    client_profile: The built/loaded profile (None until Profile Builder completes)
    profile_complete: Flag indicating Profile Builder has finished and profile is ready
    analysis_plan: Data Analyst's plan (None until Data Analyst runs)
    report: Final generated report (None until Report Builder completes)
    """

    messages: Annotated[list, add_messages]
    client_profile: ClientProfileRef | None
    profile_complete: bool
    analysis_plan: AnalysisPlan | None
    report: Report | None
