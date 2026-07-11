"""Keyword generator agent for expanding target client keywords."""

from uuid import uuid4

from langchain.agents import create_agent
from langchain.messages import HumanMessage, ToolMessage
from langchain.tools import tool, ToolRuntime
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import BaseModel, Field

from src.config import DEFAULT_MODEL, invoke_with_retry
from src.models.state import ProspectorState
from src.prompts.prompts import KEYWORD_GENERATOR_PROMPT


class ExpandedKeywords(BaseModel):
    """Response format for keyword expansion."""

    keywords: list[str] = Field(
        description="Expanded list of 10-25 keywords for profile discovery"
    )


# Lazy initialization to avoid creating agent at import time
_keyword_generator = None


def _get_keyword_generator():
    """Get or create the keyword generator agent."""
    global _keyword_generator
    if _keyword_generator is None:
        _keyword_generator = create_agent(
            model=DEFAULT_MODEL,
            response_format=ExpandedKeywords,
            state_schema=ProspectorState,
            checkpointer=InMemorySaver(),
        )
    return _keyword_generator


@tool
def get_keywords(runtime: ToolRuntime) -> Command:
    """
    Expand the list of keywords in the user persona to find more search items.

    Reads the persona from state and returns expanded keywords based on
    the user's service description and profile.

    Returns:
        Command to update state with expanded keywords
    """
    print("[get_keywords] Starting keyword generator subagent...")

    persona = runtime.state.get("user_persona")
    if persona is None:
        print("[get_keywords] No persona found in state!")
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        "No user persona found in state. Use build_persona first.",
                        tool_call_id=runtime.tool_call_id,
                    )
                ]
            }
        )

    print(f"[get_keywords] Found persona: {persona.name}")
    current_keywords = persona.target_client_keywords
    message = KEYWORD_GENERATOR_PROMPT.format(current_keywords=current_keywords)

    # Include persona context in the message
    full_message = f"""
    User Persona:
    {persona.model_dump_json(indent=2)}
    {message}
    """

    # Use isolated thread for subagent to avoid message history conflicts
    subagent_config = {"configurable": {"thread_id": f"keyword-gen-{str(uuid4())}"}}

    keyword_generator = _get_keyword_generator()
    response = invoke_with_retry(
        keyword_generator, {"messages": [HumanMessage(full_message)]}, subagent_config
    )
    print("[get_keywords] Subagent finished, parsing response...")
    keywords_content = response["messages"][-1].content

    try:
        expanded = ExpandedKeywords.model_validate_json(keywords_content)
        # Update the persona with expanded keywords
        updated_persona = persona.model_copy(
            update={"target_client_keywords": expanded.keywords}
        )
        print(f"[get_keywords] Expanded to {len(expanded.keywords)} keywords")
        return Command(
            update={
                "user_persona": updated_persona,
                "messages": [
                    ToolMessage(
                        f"Expanded keywords to {len(expanded.keywords)} items: {expanded.keywords}",
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
            }
        )
    except Exception as e:
        print(f"[get_keywords] Failed to parse keywords: {e}")
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        f"Generated keywords: {keywords_content}",
                        tool_call_id=runtime.tool_call_id,
                    )
                ]
            }
        )
