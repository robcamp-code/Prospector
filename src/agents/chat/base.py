"""Base class for LangGraph nodes backed by an LLM."""

from abc import ABC, abstractmethod

from langchain_anthropic import ChatAnthropic
from langchain_core.runnables import RunnableConfig

from src.agents.chat.graph_state import GraphState
from src.core.config import get_settings


class SubAgent(ABC):
    """Base class for a LangGraph node backed by an LLM.

    Subclasses implement __call__ so instances are directly usable as
    graph nodes: graph.add_node("name", MySubAgent()).
    """

    def __init__(self) -> None:
        model_id = get_settings().model.split(":", 1)[-1]  # "provider:model-id" -> model-id
        self.llm = ChatAnthropic(model=model_id)

    @abstractmethod
    async def __call__(self, state: GraphState, config: RunnableConfig) -> dict:
        ...
