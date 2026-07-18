"""Chat agent implementation using BaseAgent."""

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph

from src.agents.chat.prompts import SYSTEM_PROMPT
from src.core.config import get_settings
from src.core.database import get_checkpointer
from src.core.state import GlobalState


class ChatAgent:
    """Simple chat agent with conversation persistence."""

    def __init__(self, model: str | None = None):
        settings = get_settings()
        self.model = model or settings.model
        self.llm = ChatOpenAI(model=self.model, temperature=0.7)

    def _build_graph(self) -> StateGraph:
        """Build the chat agent graph."""

        def chat_node(state: GlobalState) -> GlobalState:
            """Process messages and generate a response."""
            messages = state["messages"]

            # Prepend system message if not present
            if not messages or not isinstance(messages[0], SystemMessage):
                messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)

            response = self.llm.invoke(messages)
            return {"messages": [response]}

        graph = StateGraph(GlobalState)
        graph.add_node("chat", chat_node)
        graph.set_entry_point("chat")
        graph.add_edge("chat", END)

        return graph

    async def chat(self, message: str, thread_id: str | None = None) -> dict:
        """Send a message and get a response.

        Args:
            message: User's message
            thread_id: Optional thread ID for conversation persistence.
                If None, a new unique thread ID is generated.

        Returns:
            Dict with thread_id and the assistant's response
        """
        from uuid import uuid4

        if thread_id is None:
            thread_id = str(uuid4())

        checkpointer = get_checkpointer()
        graph = self._build_graph()
        agent = graph.compile(checkpointer=checkpointer)

        config = {"configurable": {"thread_id": thread_id}}
        input_state = {"messages": [HumanMessage(content=message)]}

        final_state = None
        async for event in agent.astream(input_state, config):
            final_state = event

        return {
            "thread_id": thread_id,
            "state": final_state,
        }

    async def get_history(self, thread_id: str) -> list:
        """Get conversation history for a thread.

        Args:
            thread_id: Thread ID of the conversation

        Returns:
            List of messages in the conversation
        """
        checkpointer = get_checkpointer()
        graph = self._build_graph()
        agent = graph.compile(checkpointer=checkpointer)

        config = {"configurable": {"thread_id": thread_id}}

        state = await agent.aget_state(config)
        if state and state.values:
            return state.values.get("messages", [])
        return []
