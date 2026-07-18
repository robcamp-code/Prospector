"""SQL Analyst Agent for geographic demographic analysis."""

import os
from typing import TypedDict

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import Annotated

from src.agents.sql_analyst.models import AnalysisResult
from src.agents.sql_analyst.prompts import SYSTEM_PROMPT, get_analysis_prompt
from src.agents.sql_analyst.tools import TOOLS

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/prospector"
)


class SQLAnalystState(TypedDict):
    """State for the SQL Analyst Agent graph."""

    messages: Annotated[list, add_messages]
    profile_id: int
    target_geography: str
    geography_type: str
    analysis_result: AnalysisResult | None


class SQLAnalystAgent:
    """Agent for analyzing geographic demographics against client profiles.

    This agent:
    1. Takes a ClientProfile ID and target geography
    2. Fetches and scores all ZIP codes in that geography
    3. Aggregates results at multiple geographic levels
    4. Returns hierarchical rankings (state → cbsa → county → city → zip)
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        """Initialize the SQL Analyst Agent.

        Args:
            model: OpenAI model to use (default: gpt-4o-mini for cost efficiency)
        """
        self.model = model
        self.llm = ChatOpenAI(model=model, temperature=0)
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the agent graph with deterministic tool calling."""
        graph = StateGraph(SQLAnalystState)

        # Add nodes
        graph.add_node("analyze_request", self._analyze_request_node)
        graph.add_node("execute_analysis", ToolNode(TOOLS))
        graph.add_node("format_output", self._format_output_node)

        # Deterministic edges
        graph.set_entry_point("analyze_request")
        graph.add_edge("analyze_request", "execute_analysis")
        graph.add_edge("execute_analysis", "format_output")
        graph.add_edge("format_output", END)

        return graph

    async def _analyze_request_node(self, state: SQLAnalystState) -> dict:
        """Force call to aggregate_by_hierarchy tool."""
        profile_id = state["profile_id"]
        geography_type = state["geography_type"]
        target_geography = state["target_geography"]

        # Build fresh message sequence
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": get_analysis_prompt(
                    profile_id, geography_type, target_geography
                ),
            },
        ]

        # Force the specific tool call
        llm_forced = self.llm.bind_tools(TOOLS, tool_choice="aggregate_by_hierarchy")
        response = await llm_forced.ainvoke(messages)
        return {"messages": [response]}

    async def _format_output_node(self, state: SQLAnalystState) -> dict:
        """Generate final summary message from analysis results."""
        # Get the analysis result from state
        analysis_result = state.get("analysis_result")

        if analysis_result is None:
            # No analysis result - something went wrong
            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {
                    "role": "user",
                    "content": "The analysis did not complete successfully. Please inform the user.",
                },
            ]
        else:
            # Build summary from result
            result_dict = (
                analysis_result.model_dump()
                if hasattr(analysis_result, "model_dump")
                else analysis_result
            )

            summary_parts = [
                f"## Geographic Analysis Complete",
                f"",
                f"**Profile:** {result_dict['profile_name']} (ID: {result_dict['profile_id']})",
                f"**Target:** {result_dict['target_geography']} ({result_dict['geography_type']})",
                f"**Coverage:** {result_dict['total_zips_analyzed']:,} ZIP codes, {result_dict['total_population']:,.0f} population",
                f"",
            ]

            # Add top locations for each level
            for level, key in [
                ("Counties", "top_counties"),
                ("Cities", "top_cities"),
                ("ZIP Codes", "top_zips"),
            ]:
                locations = result_dict.get(key, [])
                if locations:
                    summary_parts.append(f"### Top {level}")
                    for loc in locations[:3]:
                        summary_parts.append(
                            f"- **{loc['name']}** - Score: {loc['score']:.1f}, "
                            f"Pop: {loc['population']:,.0f}, Income: ${loc['median_income']:,.0f}"
                        )
                    summary_parts.append("")

            messages = [
                {"role": "system", "content": "You are a helpful assistant."},
                {
                    "role": "user",
                    "content": "\n".join(summary_parts)
                    + "\n\nProvide a brief executive summary of these findings.",
                },
            ]

        response = await self.llm.ainvoke(messages)
        return {"messages": [response]}

    async def run(
        self,
        profile_id: int,
        target_geography: str,
        geography_type: str,
        thread_id: str = "default",
    ) -> dict:
        """Run the agent to analyze a geography for a profile.

        Args:
            profile_id: Database ID of the ClientProfile
            target_geography: Name of the geography to analyze
            geography_type: 'cbsa' or 'state'
            thread_id: Thread ID for conversation persistence

        Returns:
            Final state including the AnalysisResult
        """
        async with AsyncPostgresSaver.from_conn_string(DATABASE_URL) as checkpointer:
            await checkpointer.setup()

            compiled = self.graph.compile(checkpointer=checkpointer)

            config = {"configurable": {"thread_id": thread_id}}

            initial_state = {
                "messages": [
                    HumanMessage(
                        content=f"Analyze {geography_type} '{target_geography}' for profile {profile_id}"
                    )
                ],
                "profile_id": profile_id,
                "target_geography": target_geography,
                "geography_type": geography_type,
                "analysis_result": None,
            }

            # Run through all events
            async for _ in compiled.astream(initial_state, config):
                pass

            # Get the full accumulated state
            state_snapshot = await compiled.aget_state(config)
            return {
                "state": state_snapshot.values,
                "analysis_result": state_snapshot.values.get("analysis_result"),
            }

    async def run_without_checkpointer(
        self,
        profile_id: int,
        target_geography: str,
        geography_type: str,
    ) -> dict:
        """Run the agent without persistence (for testing).

        Args:
            profile_id: Database ID of the ClientProfile
            target_geography: Name of the geography to analyze
            geography_type: 'cbsa' or 'state'

        Returns:
            Final state including the AnalysisResult
        """
        compiled = self.graph.compile()

        initial_state = {
            "messages": [
                HumanMessage(
                    content=f"Analyze {geography_type} '{target_geography}' for profile {profile_id}"
                )
            ],
            "profile_id": profile_id,
            "target_geography": target_geography,
            "geography_type": geography_type,
            "analysis_result": None,
        }

        # Use ainvoke to get accumulated state
        final_state = await compiled.ainvoke(initial_state)
        return {"state": final_state, "analysis_result": final_state.get("analysis_result")}


async def run_analysis(
    profile_id: int,
    target_geography: str,
    geography_type: str,
    thread_id: str = "default",
) -> dict:
    """Convenience function to run the SQL Analyst Agent.

    Args:
        profile_id: Database ID of the ClientProfile
        target_geography: Name of the geography to analyze
        geography_type: 'cbsa' or 'state'
        thread_id: Thread ID for conversation persistence

    Returns:
        Final agent state
    """
    agent = SQLAnalystAgent()
    return await agent.run(profile_id, target_geography, geography_type, thread_id)
