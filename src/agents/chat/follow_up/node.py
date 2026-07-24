"""Follow-Up node: ask the user for missing preference fields, then end the turn."""

from langchain_core.runnables import RunnableConfig

from src.agents.chat.base import SubAgent
from src.agents.chat.follow_up import prompts
from src.agents.chat.graph_state import GraphState
from src.schemas.preferences import load_preferences


class FollowUp(SubAgent):
    """Ask one good follow-up question about missing preference fields."""

    async def __call__(self, state: GraphState, config: RunnableConfig) -> dict:
        preferences = load_preferences(state.get("preferences"))
        known = []
        if preferences:
            for field_name in ("name", "business_type", "service_description", "price_point"):
                value = getattr(preferences, field_name)
                if value:
                    known.append(f"- {field_name}: {value}")

        follow_up_prompt = prompts.FOLLOW_UP_PROMPT.format(
            missing_fields=", ".join(state.get("missing_fields", [])) or "everything",
            known_summary="\n".join(known) or "- nothing yet",
        )

        response = await self.ainvoke_with_retry(self.llm, [
            {"role": "user", "content": follow_up_prompt},
        ])

        return {"messages": [response]}
