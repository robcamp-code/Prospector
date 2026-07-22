"""Skeleton chat agent with minimal LangGraph state (messages only)."""

from uuid import uuid4

from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph
from langchain_core.messages import HumanMessage

from src.agents.chat.state import ChatState
from src.core.config import get_settings
from src.core.database import get_checkpointer


class ChatAgent:
    """Skeleton chat agent: single node, calls ChatAnthropic, Postgres checkpointer."""

    def __init__(self):
        self.settings = get_settings()
        self.llm = ChatAnthropic(model=self.settings.model)

    def _build_graph_structure(self) -> StateGraph:
        """Build a minimal StateGraph with one node: call the LLM."""
        graph = StateGraph(ChatState)

        def call_model(state: ChatState) -> dict:
            """Call the LLM on the current messages."""
            response = self.llm.invoke(state["messages"])
            return {"messages": [response]}

        graph.add_node("call_model", call_model)
        graph.add_edge("__start__", "call_model")
        graph.add_edge("call_model", "__end__")

        return graph

    async def chat(self, message: str, thread_id: str | None = None) -> dict:
        """Send a message and get a response, persisting via checkpointer.

        Args:
            message: The user's message.
            thread_id: Optional thread ID for continuing a conversation.
                If None, generates a new uuid4().

        Returns:
            Dict with "thread_id" and "state" (the final graph state).
        """
        if thread_id is None:
            thread_id = str(uuid4())

        graph = self._build_graph_structure()
        checkpointer = get_checkpointer()
        compiled = graph.compile(checkpointer=checkpointer)

        config = {"configurable": {"thread_id": thread_id}}
        state = await compiled.ainvoke(
            {"messages": [HumanMessage(content=message)]},
            config=config,
        )

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
