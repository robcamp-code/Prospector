"""Multi-node chat agent: Profile Builder → Data Analyst → Report Builder."""

from uuid import uuid4

from langchain_core.messages import HumanMessage
from langgraph.graph import StateGraph, START, END
from sqlalchemy import select

from src.agents.chat.graph_state import GraphState
from src.agents.chat.profile_builder import profile_builder
from src.agents.chat.data_analyst import data_analyst
from src.agents.chat.report_builder import (
    report_builder_llm,
    report_tools,
    finalize_report,
)
from src.core.config import get_settings
from src.core.database import get_checkpointer, AsyncSessionLocal, ClientProfile, client_profile_to_ref


class ChatAgent:
    """Multi-node agent: Profile Builder → Data Analyst → Report Builder."""

    def __init__(self):
        self.settings = get_settings()

    def _build_graph_structure(self) -> StateGraph:
        """Build StateGraph with three primary nodes and report builder sub-nodes."""
        graph = StateGraph(GraphState)

        # Add nodes
        graph.add_node("profile_builder", profile_builder)
        graph.add_node("data_analyst", data_analyst)
        graph.add_node("report_builder_llm", report_builder_llm)
        graph.add_node("report_tools", report_tools)
        graph.add_node("finalize_report", finalize_report)

        # Wiring
        graph.add_edge(START, "profile_builder")

        # Profile Builder: if incomplete, END (ask user); if complete, go to data_analyst
        graph.add_conditional_edges(
            "profile_builder",
            lambda state: "data_analyst" if state["profile_complete"] else END,
        )

        graph.add_edge("data_analyst", "report_builder_llm")

        # Report Builder loop: if tool calls, go to report_tools; else finalize
        def should_continue(state: GraphState) -> str:
            last_msg = state["messages"][-1]
            # Check if last message has tool calls
            if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                # Also check safety cap: count tool calls in message history
                tool_call_count = sum(
                    1 for msg in state["messages"]
                    if hasattr(msg, "tool_calls") and msg.tool_calls
                )
                if tool_call_count < 8:
                    return "report_tools"
            return "finalize_report"

        graph.add_conditional_edges("report_builder_llm", should_continue)
        graph.add_edge("report_tools", "report_builder_llm")  # Loop back
        graph.add_edge("finalize_report", END)

        return graph

    async def chat(self, message: str, thread_id: str | None = None) -> dict:
        """Send a message and get a response, persisting via checkpointer.

        If thread_id is provided, loads the profile from DB (source of truth).
        If None, generates a new uuid4().

        Args:
            message: The user's message.
            thread_id: Optional thread ID for continuing a conversation.

        Returns:
            Dict with "thread_id" and "state" (the final graph state).
        """
        if thread_id is None:
            thread_id = str(uuid4())

        # Load profile from DB if continuing a conversation
        profile_ref = None
        profile_complete = False

        async with AsyncSessionLocal() as session:
            stmt = select(ClientProfile).where(ClientProfile.conversation_id == thread_id)
            result = await session.execute(stmt)
            profile_row = result.scalar_one_or_none()

            if profile_row:
                profile_ref = client_profile_to_ref(profile_row)
                profile_complete = True

        # Initialize input state
        input_state = {
            "messages": [HumanMessage(content=message)],
            "client_profile": profile_ref,
            "profile_complete": profile_complete,
            "analysis_plan": None,
            "report": None,
        }

        graph = self._build_graph_structure()
        checkpointer = get_checkpointer()
        compiled = graph.compile(checkpointer=checkpointer)

        config = {"configurable": {"thread_id": thread_id}}
        state = await compiled.ainvoke(input_state, config=config)

        return {"thread_id": thread_id, "state": state}

    async def get_history(self, thread_id: str) -> list:
        """Fetch the full message history for a thread.

        Args:
            thread_id: The conversation thread ID.

        Returns:
            List of messages (empty if thread not found).
        """
        graph = self._build_graph_structure()
        checkpointer = get_checkpointer()
        compiled = graph.compile(checkpointer=checkpointer)

        config = {"configurable": {"thread_id": thread_id}}

        # Get the current state for this thread
        state = await compiled.aget_state(config)
        if state is None or not state.values:
            return []

        return state.values.get("messages", [])
