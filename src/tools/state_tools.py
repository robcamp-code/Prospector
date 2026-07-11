"""State management tools for reading and updating user persona."""

from langchain.tools import tool, ToolRuntime
from langchain.messages import ToolMessage
from langgraph.types import Command

from src.models.persona import UserPersona


@tool
def update_user_persona(user_persona: UserPersona, runtime: ToolRuntime) -> Command:
    """Update the user persona in the state."""
    return Command(
        update={
            "user_persona": user_persona,
            "messages": [
                ToolMessage(
                    "Successfully updated user persona", tool_call_id=runtime.tool_call_id
                )
            ],
        }
    )


@tool
def read_user_persona(runtime: ToolRuntime) -> str:
    """Read the user persona from state."""
    persona = runtime.state.get("user_persona")
    if persona is None:
        return "No user persona found in state. Use build_persona first."
    return persona.model_dump_json()
