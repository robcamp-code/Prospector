"""Persona builder agent for creating user personas from service descriptions."""

from uuid import uuid4

from langchain.agents import create_agent
from langchain.messages import HumanMessage, SystemMessage, ToolMessage
from langchain.tools import tool, ToolRuntime
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from src.config import DEFAULT_MODEL, invoke_with_retry
from src.models.persona import UserPersona
from src.models.state import ProspectorState
from src.prompts.prompts import USER_PERSONA_SYSTEM_PROMPT


# Lazy initialization to avoid creating agent at import time
_persona_builder = None


def _get_persona_builder():
    """Get or create the persona builder agent."""
    global _persona_builder
    if _persona_builder is None:
        _persona_builder = create_agent(
            model=DEFAULT_MODEL,
            system_prompt=SystemMessage(USER_PERSONA_SYSTEM_PROMPT),
            response_format=UserPersona,
            state_schema=ProspectorState,
            checkpointer=InMemorySaver(),
        )
    return _persona_builder


@tool
def build_persona(service_description: str, runtime: ToolRuntime) -> Command:
    """
    Build a user persona based on a simple service description.

    If the user is new and you don't have a user persona in memory,
    this is a good starting place.

    Args:
        service_description: A description of the user's service offering

    Returns:
        Command to update state with the new persona
    """
    print("[build_persona] Starting persona builder subagent...")

    # Use isolated thread for subagent to avoid message history conflicts
    subagent_config = {"configurable": {"thread_id": f"persona-builder-{str(uuid4())}"}}

    persona_builder = _get_persona_builder()
    response = invoke_with_retry(
        persona_builder, {"messages": [HumanMessage(service_description)]}, subagent_config
    )
    print("[build_persona] Subagent finished, parsing response...")
    persona_content = response["messages"][-1].content

    # Parse the response into a UserPersona and update state
    try:
        persona = UserPersona.model_validate_json(persona_content)
        print(f"[build_persona] Successfully parsed persona: {persona.name}")
        return Command(
            update={
                "user_persona": persona,
                "messages": [
                    ToolMessage(
                        f"Successfully built and saved user persona: {persona.name}",
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
            }
        )
    except Exception as e:
        print(f"[build_persona] Failed to parse persona: {e}")
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        f"Built persona but failed to save to state: {persona_content}",
                        tool_call_id=runtime.tool_call_id,
                    )
                ]
            }
        )
