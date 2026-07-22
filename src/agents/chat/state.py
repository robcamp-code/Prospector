"""State definition for the skeleton chat agent."""

from typing import Annotated

from langgraph.graph import add_messages
from typing_extensions import TypedDict


class ChatState(TypedDict):
    """Minimal chat state: just messages."""

    messages: Annotated[list, add_messages]
