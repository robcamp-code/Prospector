"""Report Builder nodes: bounded ReAct loop with get_aggregation_tool, then finalize."""

from uuid import uuid4

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import ToolMessage

from src.core.database import AsyncSessionLocal, Report
from src.agents.chat.graph_state import GraphState
from src.agents.chat.tools import get_aggregation_tool
from src.agents.chat.prompts import (
    REPORT_BUILDER_CONTEXT_PROMPT,
    FINALIZE_REPORT_PROMPT,
)
from src.core.config import get_settings
from src.schemas.report import Report as ReportSchema


async def report_builder_llm(state: GraphState, config: dict) -> dict:
    """LLM bound with get_aggregation_tool, directed by analysis plan.

    Iteratively fetches demographic data until it decides it has enough
    or hits the safety-valve cap (~8 tool calls).

    Returns: either messages with tool calls (routes to report_tools),
    or a natural response (routes to finalize_report).
    """
    model_id = get_settings().model.split(":", 1)[-1]  # Extract from "provider:model-id"
    llm = ChatAnthropic(model=model_id)
    llm_with_tools = llm.bind_tools([get_aggregation_tool])

    profile = state["client_profile"]
    plan = state["analysis_plan"]

    # Build context prompt
    context = f"""{REPORT_BUILDER_CONTEXT_PROMPT}

Client Profile:
- Business: {profile.business_type}
- Services: {profile.service_description}
- Target: {profile.name}

Analysis Plan:
- Categories: {', '.join(plan['categories'])}
- Geography Level: {plan['geography_level']}
- Location: {plan['reasoning']}

Your task: Use the get_aggregation_tool to fetch demographic data that will help build a report.
You can make multiple calls to drill down (e.g., state-level first, then counties within that state).
Stop when you have enough data for a comprehensive report (~3-5 tool calls).
When done gathering data, respond naturally (not as JSON) saying you're ready to finalize the report."""

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


async def report_tools(state: GraphState, config: dict) -> dict:
    """Execute tool calls from report_builder_llm.

    Wraps tool execution and returns results as ToolMessage objects
    to append to the message chain.
    """
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


async def finalize_report(state: GraphState, config: dict) -> dict:
    """Synthesize tool-call transcript into a structured Report; persist to DB.

    Calls LLM with with_structured_output(ReportSchema) over the full
    message transcript to generate the final report. Persists to DB.
    """
    model_id = get_settings().model.split(":", 1)[-1]  # Extract from "provider:model-id"
    llm = ChatAnthropic(model=model_id)

    profile = state["client_profile"]
    plan = state["analysis_plan"]

    # Build finalization prompt
    finalize_prompt = f"""{FINALIZE_REPORT_PROMPT}

Client: {profile.name} ({profile.business_type})
Geography: {plan['geography_level']}
Categories: {', '.join(plan['categories'])}

Using the demographic data from the conversation above, generate a comprehensive report."""

    # Invoke structured output over full message transcript
    messages = state["messages"] + [
        {"role": "system", "content": finalize_prompt},
    ]

    report = await llm.with_structured_output(ReportSchema).ainvoke(messages)

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
