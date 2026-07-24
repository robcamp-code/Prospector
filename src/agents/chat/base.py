"""Base class for LangGraph nodes backed by an LLM."""

import asyncio
from abc import ABC, abstractmethod
from typing import Any

import anthropic
from langchain_anthropic import ChatAnthropic
from langchain_core.runnables import Runnable, RunnableConfig

from src.agents.chat.graph_state import GraphState
from src.core.config import get_settings
from src.core.logging import get_logger

logger = get_logger(__name__)


class SubAgent(ABC):
    """Base class for a LangGraph node backed by an LLM.

    Subclasses implement __call__ so instances are directly usable as
    graph nodes: graph.add_node("name", MySubAgent()).
    """

    def __init__(self, **llm_kwargs) -> None:
        model_id = get_settings().model.split(":", 1)[-1]  # "provider:model-id" -> model-id
        self.llm = ChatAnthropic(model=model_id, **llm_kwargs)

    @abstractmethod
    async def __call__(self, state: GraphState, config: RunnableConfig) -> dict:
        ...

    async def ainvoke_with_retry(
        self, runnable: Runnable, messages: list, *, retries: int = 2
    ) -> Any:
        """Invoke an LLM runnable, retrying on transient Anthropic API errors.

        Anthropic's `overloaded_error` frequently arrives as an SSE `error`
        event after streaming has already started with a 200 response, which
        bypasses the SDK's own HTTP-level retry logic entirely (that logic
        only inspects the initial response status code). So we retry here
        instead, with a short exponential backoff.
        """
        for attempt in range(retries + 1):
            try:
                return await runnable.ainvoke(messages)
            except anthropic.APIStatusError:
                if attempt == retries:
                    raise
                logger.warning(
                    "Anthropic API error on attempt %d/%d; retrying",
                    attempt + 1,
                    retries + 1,
                    exc_info=True,
                )
                await asyncio.sleep(2**attempt)
