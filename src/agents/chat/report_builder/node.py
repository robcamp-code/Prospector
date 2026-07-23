"""Report Builder nodes: bounded ReAct loop with get_aggregation_tool, then finalize."""

from uuid import uuid4

from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableConfig

from src.core.database import AsyncSessionLocal, Report
from src.agents.chat.base import SubAgent
from src.agents.chat.graph_state import GraphState
from src.agents.chat.tools import get_aggregation_tool
from src.agents.chat.report_builder import prompts
from src.core.config import get_settings
from src.schemas.report import Report as ReportSchema


class ReportBuilderLLM(SubAgent):
    """LLM bound with get_aggregation_tool, directed by analysis plan.

    Iteratively fetches demographic data until it decides it has enough
    or hits the safety-valve cap (~8 tool calls).
    """

    async def __call__(self, state: GraphState, config: RunnableConfig) -> dict:
        """Fetch data using get_aggregation_tool."""
        llm_with_tools = self.llm.bind_tools([get_aggregation_tool])

        profile = state["client_profile"]
        plan = state["analysis_plan"]

        # Build context prompt
        context = prompts.REPORT_BUILDER_CONTEXT_PROMPT.format(
            business_type=profile.business_type,
            service_description=profile.service_description,
            client_name=profile.name,
            categories=", ".join(plan["categories"]),
            geography_level=plan["geography_level"],
            reasoning=plan["reasoning"],
        )

        # Call LLM with context and existing messages
        messages = state["messages"] + [
            {"role": "system", "content": context},
        ]

        response = await llm_with_tools.ainvoke(messages)

        # Check tool call count for safety valve
        tool_call_count = sum(
            1 for msg in state["messages"]
            if hasattr(msg, "tool_calls") and msg.tool_calls
        )

        if tool_call_count >= 8:
            # Force finalization; skip tool execution
            return {"messages": [response]}

        return {"messages": [response]}


class ReportToolExecutor:
    """Execute tool calls from report_builder_llm.

    Wraps tool execution and returns results as ToolMessage objects
    to append to the message chain.
    """

    async def __call__(self, state: GraphState, config: RunnableConfig) -> dict:
        """Execute tool calls."""
        tool_calls_node = state["messages"][-1]
        if not hasattr(tool_calls_node, "tool_calls"):
            return {"messages": []}

        tool_results = []
        for tool_call in tool_calls_node.tool_calls:
            try:
                result = await get_aggregation_tool.ainvoke(tool_call["args"])
                tool_results.append(
                    ToolMessage(
                        content=result,
                        tool_call_id=tool_call["id"],
                    )
                )
            except Exception as exc:
                tool_results.append(
                    ToolMessage(
                        content=f"Error executing tool: {str(exc)}",
                        tool_call_id=tool_call["id"],
                    )
                )

        return {"messages": tool_results}


class FinalizeReport(SubAgent):
    """Synthesize tool-call transcript into a structured Report; persist to DB."""

    async def __call__(self, state: GraphState, config: RunnableConfig) -> dict:
        """Synthesize tool-call transcript into a structured Report; persist to DB.

        Calls LLM with with_structured_output(ReportSchema) over the full
        message transcript to generate the final report. Persists to DB.
        """
        profile = state["client_profile"]
        plan = state["analysis_plan"]

        # Build finalization prompt
        finalize_prompt = prompts.FINALIZE_REPORT_PROMPT.format(
            client_name=profile.name,
            business_type=profile.business_type,
            geography_level=plan["geography_level"],
            categories=", ".join(plan["categories"]),
        )

        # Invoke structured output over full message transcript
        messages = state["messages"] + [
            {"role": "system", "content": finalize_prompt},
        ]

        report = await self.llm.with_structured_output(ReportSchema).ainvoke(messages)

        # Persist to DB
        thread_id = config["configurable"]["thread_id"]
        async with AsyncSessionLocal() as session:
            db_report = Report(
                id=report.report_id or str(uuid4()),
                client_profile_id=profile.profile_id,
                conversation_id=thread_id,
                title=report.title,
                subtitle=report.subtitle,
                geography_type=plan["geography_level"],
                geography_value=f"{', '.join(plan['categories'])} analysis",
                summary=report.summary.model_dump() if report.summary else {},
                sections=[s.model_dump() for s in report.sections] if report.sections else [],
            )
            session.add(db_report)
            await session.commit()

        return {"report": report}
