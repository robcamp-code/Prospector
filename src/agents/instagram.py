"""Instagram agent for generating leads from Instagram."""

from uuid import uuid4

from langchain.agents import create_agent
from langchain.messages import HumanMessage, SystemMessage
from langchain.tools import tool, ToolRuntime
from langgraph.checkpoint.memory import InMemorySaver

from src.config import DEFAULT_MODEL, invoke_with_retry
from src.models.state import ProspectorState
from src.prompts.prompts import INSTAGRAM_AGENT_SYSTEM_PROMPT
from src.tools.instagram_tools import search_ig_profiles


_ig_agent = None


def _get_ig_agent():
    """Get or create the Instagram agent."""
    global _ig_agent
    if _ig_agent is None:
        _ig_agent = create_agent(
            system_prompt=SystemMessage(INSTAGRAM_AGENT_SYSTEM_PROMPT),
            model=DEFAULT_MODEL,
            tools=[search_ig_profiles],
            state_schema=ProspectorState,
            checkpointer=InMemorySaver(),
        )
    return _ig_agent


@tool
def generate_leads_from_ig(runtime: ToolRuntime) -> str:
    """
    Generate leads from Instagram.

    Reads the user persona from state and searches for relevant
    Instagram profiles based on target keywords and locations.

    Returns:
        String containing the agent's response with found leads
    """
    print("[generate_leads_from_ig] Starting Instagram subagent...")

    persona = runtime.state.get("user_persona")
    if persona is None:
        print("[generate_leads_from_ig] No persona found in state!")
        return "No user persona found in state. Use build_persona first."

    print(f"[generate_leads_from_ig] Found persona: {persona.name}")

    # Pass persona directly in the message since subagent has isolated state
    message = f"""Your goal is to generate a list of leads based on this user persona:

    {persona.model_dump_json(indent=2)}

    Search for relevant Instagram profiles using the search_ig_profiles tool based on
    the target_client_keywords and preferred_client_locations."""

    # Use isolated thread for subagent to avoid message history conflicts
    subagent_config = {"configurable": {"thread_id": f"ig-agent-{str(uuid4())}"}}

    print("[generate_leads_from_ig] Invoking ig_agent...")
    ig_agent = _get_ig_agent()
    response = invoke_with_retry(
        ig_agent, {"messages": [HumanMessage(message)]}, subagent_config
    )
    print("[generate_leads_from_ig] Subagent finished")
    return response["messages"][-1].content
