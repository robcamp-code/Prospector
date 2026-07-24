"""Profile Builder node: extract typed Preferences, merge with stored profile, persist."""

from langchain_core.runnables import RunnableConfig

from src.agents.chat.base import SubAgent
from src.agents.chat.graph_state import GraphState
from src.agents.chat.profile_builder import prompts
from src.core.database import (
    AsyncSessionLocal,
    ClientProfile,
    get_profile_by_conversation_id,
)
from src.schemas.preferences import Preferences, load_preferences


class ProfileBuilder(SubAgent):
    """Extract typed Preferences from the conversation and persist the profile."""

    async def __call__(self, state: GraphState, config: RunnableConfig) -> dict:
        """Extract preferences; merge with any stored ones; upsert the ClientProfile.

        Routing happens on the returned profile_complete flag: complete goes to
        the data analyst, incomplete to the follow-up question node.
        """
        conversation = "\n".join(
            f"{msg.type}: {msg.content}" for msg in state["messages"] if msg.content
        )
        discovery_prompt = prompts.DISCOVERY_PROMPT.format(conversation=conversation)

        preferences = await self.ainvoke_with_retry(
            self.llm.with_structured_output(Preferences),
            [{"role": "user", "content": discovery_prompt}],
        )

        # Merge with previously stored preferences (new extraction wins per field)
        existing = load_preferences(state.get("preferences"))
        if existing:
            preferences = preferences.merge_missing_from(existing)

        if not preferences.is_complete():
            return {
                "preferences": preferences.model_dump(),
                "profile_complete": False,
                "missing_fields": preferences.missing_fields(),
            }

        # conversation_id is unique: on a resumed conversation a profile already
        # exists, so update it instead of inserting a duplicate.
        thread_id = config["configurable"]["thread_id"]
        async with AsyncSessionLocal() as session:
            profile = await get_profile_by_conversation_id(session, thread_id)
            if profile is None:
                profile = ClientProfile(
                    name=preferences.name or "Unknown",
                    conversation_id=thread_id,
                )
                session.add(profile)
            profile.name = preferences.name or "Unknown"
            profile.business_type = preferences.business_type
            profile.service_description = preferences.service_description
            profile.preferences = preferences.model_dump()
            await session.commit()
            profile_id = profile.id

        return {
            "profile_id": profile_id,
            "preferences": preferences.model_dump(),
            "profile_complete": True,
            "missing_fields": [],
        }
