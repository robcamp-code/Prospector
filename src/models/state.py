"""State schema for the Prospector multi-agent system."""

from langchain.agents import AgentState

from src.models.persona import UserPersona
from src.models.crm import CRMRow


class ProspectorState(AgentState):
    """Custom state schema for the Prospector multi-agent system."""

    user_persona: UserPersona | None = None
    output_crm: list[CRMRow] = []
