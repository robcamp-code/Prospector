"""Orchestrator agent that coordinates all other agents."""

from langchain.agents import create_agent
from langchain.messages import SystemMessage
from langgraph.checkpoint.memory import InMemorySaver

from src.config import DEFAULT_MODEL
from src.models.state import ProspectorState
from src.prompts.prompts import ORCHESTRATOR_SYSTEM_PROMPT
from src.tools.state_tools import read_user_persona
from src.tools.crm_tools import add_leads_to_crm, read_crm, export_crm_to_csv
from src.agents.persona_builder import build_persona
from src.agents.keyword_generator import get_keywords
from src.agents.instagram import generate_leads_from_ig
from src.agents.google import generate_leads_from_google


def create_orchestrator(checkpointer=None):
    """
    Create the orchestrator agent that coordinates lead generation.

    Args:
        checkpointer: Optional checkpointer for state persistence.
                     Uses InMemorySaver if not provided.

    Returns:
        The configured orchestrator agent
    """
    if checkpointer is None:
        checkpointer = InMemorySaver()

    orchestrator = create_agent(
        system_prompt=SystemMessage(ORCHESTRATOR_SYSTEM_PROMPT),
        model=DEFAULT_MODEL,
        tools=[
            build_persona,
            read_user_persona,
            get_keywords,
            generate_leads_from_ig,
            generate_leads_from_google,
            add_leads_to_crm,
            read_crm,
            export_crm_to_csv,
        ],
        state_schema=ProspectorState,
        checkpointer=checkpointer,
    )

    return orchestrator
