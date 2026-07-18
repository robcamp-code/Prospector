"""User Persona Agent for building client profiles."""

import os
from typing import TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from pydantic import BaseModel, Field
from typing_extensions import Annotated

from src.v0.agents.user_persona.prompts import (
    RESPOND_PROMPT,
    VALID_PLACE_TYPES,
    get_place_type_sync_prompt,
    get_save_profile_prompt,
    get_system_prompt,
)
from src.v0.agents.user_persona.tools import TOOLS

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/prospector"
)


class PlaceTypeMapping(BaseModel):
    """Structured output for place type analysis."""

    competitor_types: list[str] = Field(
        description="3-7 Google Places API types for direct competitors"
    )
    complementary_types: list[str] = Field(
        description="3-7 Google Places API types for complementary businesses"
    )


class IdealCustomer(BaseModel):
    """Structured output for ideal customer demographics."""

    target_income_min: int = Field(
        description="Minimum target annual household income in USD"
    )
    target_income_max: int = Field(
        description="Maximum target annual household income in USD"
    )
    target_age_min: int = Field(description="Minimum target customer age")
    target_age_max: int = Field(description="Maximum target customer age")
    target_home_ownership_min: float = Field(
        ge=0.0, le=1.0, description="Minimum home ownership rate (0.0-1.0)"
    )
    target_education_min: float = Field(
        ge=0.0, le=1.0, description="Minimum education level (0.0-1.0)"
    )


class AgentState(TypedDict):
    """State for the User Persona Agent graph."""

    messages: Annotated[list, add_messages]
    business_query: str
    ideal_customer: IdealCustomer | None
    place_types: PlaceTypeMapping | None
    profile_id: int | None


class UserPersonaAgent:
    """Agent for creating client profiles from business descriptions.

    This agent analyzes business descriptions to:
    1. Create ideal customer demographics
    2. Identify competitor and complementary place types
    3. Save the complete ClientProfile to the database
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        """Initialize the User Persona Agent.

        Args:
            model: OpenAI model to use (default: gpt-4o-mini for cost efficiency)
        """
        self.model = model
        self.llm = ChatOpenAI(model=model, temperature=0)
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the agent graph with deterministic tool calling."""
        graph = StateGraph(AgentState)

        # Add nodes
        graph.add_node("analyze", self._analyze_node)
        graph.add_node("save_profile", self._save_profile_node)
        graph.add_node("execute_save", ToolNode(TOOLS))
        graph.add_node("respond", self._respond_node)

        # Deterministic edges - no conditionals needed
        graph.set_entry_point("analyze")
        graph.add_edge("analyze", "save_profile")
        graph.add_edge("save_profile", "execute_save")
        graph.add_edge("execute_save", "respond")
        graph.add_edge("respond", END)

        return graph

    def _filter_messages(self, messages: list) -> list:
        """Filter out incomplete tool call sequences from messages.

        OpenAI requires that every tool_call has a corresponding tool response.
        This filters out any dangling tool calls without responses.
        """
        filtered = []
        for msg in messages:
            # Skip assistant messages with tool_calls that don't have responses
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                # Check if the next message(s) contain the tool responses
                # For simplicity, skip any message with tool_calls in this flow
                continue
            # Skip tool response messages (they're orphaned without their tool_calls)
            if hasattr(msg, "type") and msg.type == "tool":
                continue
            filtered.append(msg)
        return filtered

    async def _analyze_node(self, state: AgentState) -> dict:
        """Analyze the business query and determine ideal customer profile."""
        # Get the original business query (first human message)
        business_query = state.get("business_query", "")

        # Build fresh messages - don't use accumulated history
        messages = [
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": business_query},
        ]

        response = await self.llm.ainvoke(messages)
        return {"messages": [response]}

    async def _save_profile_node(self, state: AgentState) -> dict:
        """Force the model to call save_client_profile tool."""
        # Get the business query and analysis from state
        business_query = state.get("business_query", "")

        # Get the last assistant message (the analysis)
        analysis_content = ""
        for msg in reversed(state["messages"]):
            if hasattr(msg, "content") and not hasattr(msg, "tool_calls"):
                analysis_content = msg.content
                break

        # Build fresh message sequence for tool calling
        messages = [
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": business_query},
            {"role": "assistant", "content": analysis_content},
            {"role": "user", "content": get_save_profile_prompt()},
        ]

        # Use tool_choice to FORCE the specific tool call
        llm_forced = self.llm.bind_tools(
            TOOLS,
            tool_choice="save_client_profile"
        )
        response = await llm_forced.ainvoke(messages)
        return {"messages": [response]}

    async def _respond_node(self, state: AgentState) -> dict:
        """Generate final response after saving the profile."""
        # Get tool result from execute_save
        tool_result = ""
        for msg in reversed(state["messages"]):
            if hasattr(msg, "type") and msg.type == "tool":
                tool_result = msg.content
                break
            if hasattr(msg, "content") and "Successfully created" in str(msg.content):
                tool_result = msg.content
                break

        # Build fresh message sequence for response
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": f"The client profile was saved. Result: {tool_result}\n\n{RESPOND_PROMPT}"},
        ]

        response = await self.llm.ainvoke(messages)
        return {"messages": [response]}

    async def run(self, query: str, thread_id: str = "default") -> dict:
        """Run the agent on a business query.

        Args:
            query: Business description/query to analyze
            thread_id: Thread ID for conversation persistence

        Returns:
            Final state including the created profile ID
        """
        async with AsyncPostgresSaver.from_conn_string(DATABASE_URL) as checkpointer:
            await checkpointer.setup()

            compiled = self.graph.compile(checkpointer=checkpointer)

            config = {"configurable": {"thread_id": thread_id}}

            initial_state = {
                "messages": [HumanMessage(content=query)],
                "business_query": query,
                "ideal_customer": None,
                "place_types": None,
                "profile_id": None,
            }

            # Run through all events
            async for _ in compiled.astream(initial_state, config):
                pass

            # Get the full accumulated state
            state_snapshot = await compiled.aget_state(config)
            return {"state": state_snapshot.values, "profile_id": state_snapshot.values.get("profile_id")}

    async def run_without_checkpointer(self, query: str) -> dict:
        """Run the agent without persistence (for testing).

        Args:
            query: Business description/query to analyze

        Returns:
            Final state including the created profile ID
        """
        compiled = self.graph.compile()

        initial_state = {
            "messages": [HumanMessage(content=query)],
            "business_query": query,
            "ideal_customer": None,
            "place_types": None,
            "profile_id": None,
        }

        # Use ainvoke to get accumulated state
        final_state = await compiled.ainvoke(initial_state)
        return {"state": final_state, "profile_id": final_state.get("profile_id")}

    def get_place_types_sync(self, service_description: str) -> PlaceTypeMapping:
        """Synchronous method to get place types for a business.

        This is a simpler, non-agentic method for getting place type mappings.

        Args:
            service_description: Natural language description of the business

        Returns:
            PlaceTypeMapping with competitor and complementary types
        """
        prompt = get_place_type_sync_prompt(service_description)
        llm_structured = self.llm.with_structured_output(PlaceTypeMapping)
        result = llm_structured.invoke(prompt)

        # Validate types
        result.competitor_types = [
            t for t in result.competitor_types if t in VALID_PLACE_TYPES
        ]
        result.complementary_types = [
            t for t in result.complementary_types if t in VALID_PLACE_TYPES
        ]

        return result


async def run_agent(query: str, thread_id: str = "default") -> dict:
    """Convenience function to run the User Persona Agent.

    Args:
        query: Business description/query to analyze
        thread_id: Thread ID for conversation persistence

    Returns:
        Final agent state
    """
    agent = UserPersonaAgent()
    return await agent.run(query, thread_id)
