"""Graph state for the chat agent.

Only JSON-serializable values cross node boundaries: preferences and the
query plan are stored as plain dicts (model_dump()) and revalidated at each
node's boundary via load_preferences / QueryPlan.model_validate. Query
*results* never enter state — they stay local to the report generator.
"""

from typing import Annotated

from langgraph.graph import add_messages
from typing_extensions import TypedDict

from src.schemas.report import Report


class GraphState(TypedDict):
    """State shared across graph nodes.

    messages: Conversation history (LangChain messages, add_messages reducer)
    profile_id: DB id of the persisted ClientProfile (None until first save)
    preferences: Preferences.model_dump() (None until extracted; revalidate on read)
    profile_complete: True once all required preference fields are present
    missing_fields: Preference fields still to ask the user about
    query_plan: QueryPlan.model_dump() (None until Data Analyst runs)
    report: Final generated report (None until Report Generator completes)
    """

    messages: Annotated[list, add_messages]
    profile_id: str | None
    preferences: dict | None
    profile_complete: bool
    missing_fields: list[str]
    query_plan: dict | None
    report: Report | None
