"""Orchestrator agent for managing Prospector workflow."""

import os
from uuid import uuid4

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.prebuilt import create_react_agent

from src.agents.orchestrator.prompts import ORCHESTRATOR_SYSTEM_PROMPT
from src.agents.orchestrator.state import ProspectorState
from src.agents.orchestrator.tools import ORCHESTRATOR_TOOLS

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/prospector"
)


def create_orchestrator(checkpointer=None, model: str = "gpt-5.5"):
    """Create the orchestrator agent graph.

    Uses LangGraph's create_react_agent for LLM-driven tool routing.

    Args:
        checkpointer: Optional checkpointer for state persistence.
            If None, no persistence is used.
        model: OpenAI model to use (default: gpt-5)

    Returns:
        Compiled LangGraph agent
    """
    llm = ChatOpenAI(model=model, temperature=0)

    return create_react_agent(
        model=llm,
        tools=ORCHESTRATOR_TOOLS,
        state_schema=ProspectorState,
        checkpointer=checkpointer,
        prompt=ORCHESTRATOR_SYSTEM_PROMPT,
    )


class Orchestrator:
    """Wrapper class for the orchestrator agent with lifecycle management.

    This class provides a simple interface for running the orchestrator
    with automatic checkpointer setup and teardown.
    """

    def __init__(self, model: str = "gpt-5.5"):
        """Initialize the Orchestrator.

        Args:
            model: OpenAI model to use (default: gpt-5)
        """
        self.model = model

    async def run(self, query: str, thread_id: str | None = None) -> dict:
        """Run the orchestrator on a user query.

        Args:
            query: User's message/query
            thread_id: Optional thread ID for conversation persistence.
                If None, a new unique thread ID is generated.

        Returns:
            Final agent state including messages and any updated state
        """
        if thread_id is None:
            thread_id = f"orchestrator-{str(uuid4())}"

        async with AsyncPostgresSaver.from_conn_string(DATABASE_URL) as checkpointer:
            await checkpointer.setup()

            agent = create_orchestrator(checkpointer=checkpointer, model=self.model)

            config = {"configurable": {"thread_id": thread_id}}

            initial_state = {
                "messages": [HumanMessage(content=query)],
                "client_profile": None,
                "current_task": None,
                "target_location": None,
            }

            # Stream through the agent and collect final state
            final_state = None
            async for event in agent.astream(initial_state, config):
                final_state = event

            return {
                "thread_id": thread_id,
                "state": final_state,
            }

    async def continue_conversation(self, query: str, thread_id: str) -> dict:
        """Continue an existing conversation.

        Args:
            query: User's follow-up message
            thread_id: Thread ID of the existing conversation

        Returns:
            Final agent state
        """
        async with AsyncPostgresSaver.from_conn_string(DATABASE_URL) as checkpointer:
            await checkpointer.setup()

            agent = create_orchestrator(checkpointer=checkpointer, model=self.model)

            config = {"configurable": {"thread_id": thread_id}}

            # For continuation, just send the new message
            input_state = {
                "messages": [HumanMessage(content=query)],
            }

            final_state = None
            async for event in agent.astream(input_state, config):
                final_state = event

            return {
                "thread_id": thread_id,
                "state": final_state,
            }

    async def run_without_checkpointer(self, query: str) -> dict:
        """Run the orchestrator without persistence (for testing).

        Args:
            query: User's message/query

        Returns:
            Final agent state
        """
        agent = create_orchestrator(checkpointer=None, model=self.model)

        initial_state = {
            "messages": [HumanMessage(content=query)],
            "client_profile": None,
            "current_task": None,
            "target_location": None,
        }

        final_state = None
        async for event in agent.astream(initial_state):
            final_state = event

        return {"state": final_state}
