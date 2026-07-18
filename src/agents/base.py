"""BaseAgent class eliminating checkpointer boilerplate."""

from abc import ABC, abstractmethod
from uuid import uuid4

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph

from src.core.config import get_settings
from src.core.database import get_checkpointer
from src.core.state import GlobalState


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    def __init__(self, model: str | None = None):
        settings = get_settings()
        self.model_name = model or settings.model
        self.llm = ChatOpenAI(model=self.model_name, temperature=0)
        self.graph = self._build_graph()

    @abstractmethod
    def _build_graph(self) -> StateGraph:
        """Build and return the agent's state graph."""
        pass

    @abstractmethod
    def _get_initial_state(self, **kwargs) -> GlobalState:
        """Return the initial state for the agent."""
        pass

    async def run(self, thread_id: str | None = None, **kwargs) -> dict:
        """Run the agent with automatic checkpointing."""
        if thread_id is None:
            thread_id = str(uuid4())

        checkpointer = get_checkpointer()
        compiled = self.graph.compile(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": thread_id}}
        async for _ in compiled.astream(self._get_initial_state(**kwargs), config):
            pass
        state = await compiled.aget_state(config)
        return {"thread_id": thread_id, "state": state.values}
