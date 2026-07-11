"""Google agent for generating leads from YouTube and Google Maps."""

from uuid import uuid4

from langchain.agents import create_agent
from langchain.messages import HumanMessage, SystemMessage
from langchain.tools import tool, ToolRuntime
from langgraph.checkpoint.memory import InMemorySaver

from src.config import DEFAULT_MODEL, invoke_with_retry
from src.models.state import ProspectorState
from src.prompts.prompts import GOOGLE_AGENT_SYSTEM_PROMPT
from src.tools.google_tools import search_youtube, search_google_maps


# Lazy initialization to avoid creating agent at import time
_google_agent = None


def _get_google_agent():
    """Get or create the Google agent."""
    global _google_agent
    if _google_agent is None:
        _google_agent = create_agent(
            system_prompt=SystemMessage(GOOGLE_AGENT_SYSTEM_PROMPT),
            model=DEFAULT_MODEL,
            tools=[search_youtube, search_google_maps],
            state_schema=ProspectorState,
            checkpointer=InMemorySaver(),
        )
    return _google_agent


@tool
def generate_leads_from_google(runtime: ToolRuntime) -> str:
    """
    Generate leads from YouTube and Google Maps.

    Reads the user persona from state and searches for relevant
    YouTube channels and Google Maps businesses based on target keywords and locations.

    Returns:
        String containing the agent's response with found leads
    """
    print("[generate_leads_from_google] Starting Google subagent...")

    persona = runtime.state.get("user_persona")
    if persona is None:
        print("[generate_leads_from_google] No persona found in state!")
        return "No user persona found in state. Use build_persona first."

    print(f"[generate_leads_from_google] Found persona: {persona.name}")

    # Pass persona directly in the message since subagent has isolated state
    message = f"""Your goal is to generate leads from YouTube and Google Maps based on this user persona:

    {persona.model_dump_json(indent=2)}

    1. Use search_youtube to find relevant YouTube channels and content creators
       that match the target_client_keywords.

    2. Use search_google_maps to find local businesses in the preferred_client_locations
       that match the target client profile.

    Search for leads that would be good potential clients based on the persona's
    industry, target_client_size, and service_type."""

    # Use isolated thread for subagent to avoid message history conflicts
    subagent_config = {"configurable": {"thread_id": f"google-agent-{str(uuid4())}"}}

    print("[generate_leads_from_google] Invoking google_agent...")
    google_agent = _get_google_agent()
    response = invoke_with_retry(
        google_agent, {"messages": [HumanMessage(message)]}, subagent_config
    )
    print("[generate_leads_from_google] Subagent finished")
    return response["messages"][-1].content
