"""Done Message node: append a templated closing message. No LLM call."""

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from src.agents.chat.done_message import templates
from src.agents.chat.graph_state import GraphState
from src.schemas.preferences import LocationPreference, load_preferences


class DoneMessage:
    """Tell the user their report is ready (skipped if no report was produced)."""

    async def __call__(self, state: GraphState, config: RunnableConfig) -> dict:
        report = state.get("report")
        if report is None:
            # report_generator already appended its no-data explanation
            return {"messages": []}

        preferences = load_preferences(state.get("preferences"))
        location = (preferences.location if preferences else None) or LocationPreference()

        message = templates.REPORT_READY_TEMPLATE.format(
            title=report.title,
            scope=location.describe(),
            section_count=len(report.sections),
        )
        return {"messages": [AIMessage(content=message)]}
