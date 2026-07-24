"""Chat agent graph: Profile Builder → Data Analyst → Report Generator → Done.

Linear pipeline with a single branch: an incomplete profile routes to a
follow-up question and ends the turn. No tool loops — the Data Analyst plans
typed queries and the Report Generator executes them deterministically.
"""

from uuid import uuid4

from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END

from src.agents.chat.data_analyst import DataAnalyst
from src.agents.chat.done_message import DoneMessage
from src.agents.chat.follow_up import FollowUp
from src.agents.chat.graph_state import GraphState
from src.agents.chat.profile_builder import ProfileBuilder
from src.agents.chat.report_generator import ReportGenerator
from src.agents.chat.visualize import _visualize
from src.core.database import (
    AsyncSessionLocal,
    get_checkpointer,
    get_profile_by_conversation_id,
)
from src.schemas.preferences import load_preferences


class ChatAgent:
    """Profile Builder → (Follow Up | Data Analyst → Report Generator → Done)."""

    def _build_graph_structure(self) -> StateGraph:
        graph = StateGraph(GraphState)

        graph.add_node("profile_builder", ProfileBuilder())
        graph.add_node("follow_up", FollowUp())
        graph.add_node("data_analyst", DataAnalyst())
        graph.add_node("report_generator", ReportGenerator())
        graph.add_node("done_message", DoneMessage())

        graph.add_edge(START, "profile_builder")
        graph.add_conditional_edges(
            "profile_builder",
            lambda state: "data_analyst" if state["profile_complete"] else "follow_up",
            {"data_analyst": "data_analyst", "follow_up": "follow_up"},
        )
        graph.add_edge("follow_up", END)
        graph.add_edge("data_analyst", "report_generator")
        graph.add_edge("report_generator", "done_message")
        graph.add_edge("done_message", END)

        return graph

    async def chat(self, message: str, thread_id: str | None = None) -> dict:
        """Send a message and get a response, persisting via checkpointer.

        If thread_id is provided, loads stored preferences from the DB
        (source of truth). If None, generates a new uuid4().
        """
        if thread_id is None:
            thread_id = str(uuid4())

        # Load stored preferences if continuing a conversation. Preferences are
        # revalidated (load_preferences): rows written under an older schema
        # come back as None and are simply re-extracted.
        profile_id = None
        preferences = None
        async with AsyncSessionLocal() as session:
            profile_row = await get_profile_by_conversation_id(session, thread_id)
            if profile_row:
                profile_id = profile_row.id
                loaded = load_preferences(profile_row.preferences)
                if loaded:
                    preferences = loaded.model_dump()

        input_state = {
            "messages": [HumanMessage(content=message)],
            "profile_id": profile_id,
            "preferences": preferences,
            "profile_complete": False,
            "missing_fields": [],
            "query_plan": None,
            "report": None,
        }

        graph = self._build_graph_structure()
        compiled = graph.compile(checkpointer=get_checkpointer())

        config = {
            "configurable": {"thread_id": thread_id},
            "run_name": "prospector-chat",
            "tags": ["chat"],
        }
        state = await compiled.ainvoke(input_state, config=config)

        return {"thread_id": thread_id, "state": state}

    async def get_history(self, thread_id: str) -> list:
        """Fetch the full message history for a thread (empty if not found)."""
        graph = self._build_graph_structure()
        compiled = graph.compile(checkpointer=get_checkpointer())

        config = {"configurable": {"thread_id": thread_id}}
        state = await compiled.aget_state(config)
        if state is None or not state.values:
            return []

        return state.values.get("messages", [])

    def visualize(self, output_dir: str = "docs", filename: str = "agent-graph.png") -> str:
        """Generate and save a visual representation of the graph."""
        graph = self._build_graph_structure()
        try:
            compiled = graph.compile(checkpointer=get_checkpointer())
        except RuntimeError:
            # Checkpointer not initialized; compile without it for visualization
            compiled = graph.compile()
        return _visualize(compiled, output_dir=output_dir, filename=filename)
