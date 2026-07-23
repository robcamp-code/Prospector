"""Profile Builder node: extract business info, ask follow-ups if incomplete, persist profile."""

from pydantic import BaseModel
from langchain_core.runnables import RunnableConfig

from src.core.database import AsyncSessionLocal, ClientProfile, DemographicTarget, client_profile_to_ref
from src.agents.chat.base import SubAgent
from src.agents.chat.graph_state import GraphState
from src.agents.chat.profile_builder import prompts


class Preferences(BaseModel):
    """Extracted preferences from conversation."""

    name: str | None = None
    business_type: str | None = None
    services_products: str | None = None
    price_point: str | None = None
    target_customer_description: str | None = None
    location_preference: str | None = None
    demographic_interests: str | None = None

    def is_complete(self) -> bool:
        """Check if all required fields are populated."""
        return all([
            self.name and self.name.strip(),
            self.business_type and self.business_type.strip(),
            self.services_products and self.services_products.strip(),
            self.price_point and self.price_point.strip(),
            self.target_customer_description and self.target_customer_description.strip(),
            self.location_preference and self.location_preference.strip(),
            self.demographic_interests and self.demographic_interests.strip(),
        ])

    def missing_fields(self) -> list[str]:
        """List missing required fields."""
        fields = [
            ("name", self.name),
            ("business_type", self.business_type),
            ("services_products", self.services_products),
            ("price_point", self.price_point),
            ("target_customer_description", self.target_customer_description),
            ("location_preference", self.location_preference),
            ("demographic_interests", self.demographic_interests),
        ]
        return [name for name, value in fields if not value or not value.strip()]


class ProfileBuilder(SubAgent):
    """Extract and validate business profile, or ask for clarification."""

    async def __call__(self, state: GraphState, config: RunnableConfig) -> dict:
        """Extract and validate business profile, or ask for clarification.

        If profile is complete, persist to DB and return it.
        If incomplete, ask LLM for a follow-up question and return incomplete state.
        """
        # Extract preferences from message history
        conversation = "\n".join(f"{msg.type}: {msg.content}" for msg in state["messages"])
        discovery_prompt = prompts.DISCOVERY_PROMPT.format(conversation=conversation)

        preferences = await self.llm.with_structured_output(Preferences).ainvoke([
            {"role": "user", "content": discovery_prompt},
        ])

        # Merge with existing profile if any
        if state["client_profile"]:
            existing = state["client_profile"]
            preferences.name = preferences.name or existing.name
            preferences.business_type = preferences.business_type or existing.business_type
            preferences.services_products = preferences.services_products or existing.service_description
            preferences.location_preference = preferences.location_preference or existing.location_preference
            # Keep existing demographic interests if none extracted in new message
            if not preferences.demographic_interests and existing.target_demographics:
                preferences.demographic_interests = "; ".join(t.demographic_key for t in existing.target_demographics)

        # Check completeness
        if preferences.is_complete():
            # Persist to DB
            thread_id = config["configurable"]["thread_id"]
            async with AsyncSessionLocal() as session:
                # Create ClientProfile
                profile = ClientProfile(
                    name=preferences.name or "Unknown",
                    business_type=preferences.business_type,
                    service_description=preferences.services_products,
                    conversation_id=thread_id,
                    location_preference=preferences.location_preference,
                )
                session.add(profile)
                await session.flush()  # Get the ID

                # Parse demographic interests and create DemographicTarget rows
                created_targets = []
                if preferences.demographic_interests:
                    interests = [s.strip() for s in preferences.demographic_interests.split(",")]
                    for interest in interests:
                        # Try to map interest to a demographic_key via keyword matching
                        key = _match_demographic_key(interest)
                        if key:
                            target = DemographicTarget(
                                client_profile_id=profile.id,
                                demographic_key=key,
                                constraint_type="range",
                                importance_weight=0.5,
                            )
                            session.add(target)
                            created_targets.append(target)

                await session.commit()

                # Manually set the relationship to avoid lazy-loading after session closes
                profile.target_demographics = created_targets

                # Convert to ref for state
                profile_ref = client_profile_to_ref(profile)

            return {
                "client_profile": profile_ref,
                "profile_complete": True,
            }

        else:
            # Ask for missing field
            missing = preferences.missing_fields()
            follow_up_prompt = prompts.ASK_USER_FOR_MISSING_PREFERENCES.format(
                missing_fields=", ".join(missing)
            )

            response = await self.llm.ainvoke([
                {"role": "user", "content": follow_up_prompt},
            ])

            return {
                "messages": [response],
                "profile_complete": False,
            }


def _match_demographic_key(interest_text: str) -> str | None:
    """Try to map free-text interest to a demographic_key in DEMOGRAPHICS.

    Very basic pattern matching; real implementation would be more sophisticated (LLM).
    """
    interest_lower = interest_text.lower()

    # Simple keyword matching
    keywords = {
        "young": "age",
        "age": "age",
        "professional": "education",
        "educated": "education",
        "college": "education",
        "income": "income",
        "wealthy": "income",
        "rich": "income",
        "family": "marital_status",
        "married": "marital_status",
        "home": "housing",
        "house": "housing",
        "health": "health",
        "fit": "health",
        "language": "language",
        "spanish": "language",
        "bilingual": "language",
        "race": "race",
        "ethnicity": "race",
        "hispanic": "race",
        "latino": "race",
        "transport": "transportation",
        "commute": "transportation",
        "car": "transportation",
        "employ": "employment",
        "work": "employment",
    }

    for keyword, key in keywords.items():
        if keyword in interest_lower:
            return key

    return None
