"""Tools for the ProfileBuilder agent."""

from typing import Literal

from langchain_core.messages import ToolMessage
from langchain_core.tools import tool
from langgraph.types import Command

from src.models.client_profile import ClientProfile, DemographicTarget
from src.v0.models.base import SessionLocal


@tool
def save_client_profile(
    name: str,
    business_type: str,
    service_description: str,
    competitor_types: list[str],
    complimentary_types: list[str],
    conversation_id: str | None = None,
) -> Command[Literal["analyze_and_save"]]:
    """Save a client profile to the database.

    Args:
        name: Business name
        business_type: Type/category of business (e.g., "fitness", "restaurant")
        service_description: Full description of the business and services
        competitor_types: List of Google Places API types for competitors
        complimentary_types: List of Google Places API types for complementary businesses
        conversation_id: Optional conversation ID to link this profile to

    Returns:
        Command with profile_id in state update
    """
    session = SessionLocal()
    try:
        profile = ClientProfile(
            name=name,
            business_type=business_type,
            service_description=service_description,
            conversation_id=conversation_id,
            competitor_types=competitor_types,
            complimentary_types=complimentary_types,
        )
        session.add(profile)
        session.commit()
        session.refresh(profile)

        return Command(
            update={
                "profile_id": profile.id,
                "messages": [
                    ToolMessage(
                        content=f"Profile created successfully with ID {profile.id}",
                        tool_call_id="save_client_profile",
                    )
                ],
            },
            goto="analyze_and_save",
        )
    except Exception as e:
        session.rollback()
        return Command(
            update={
                "error": str(e),
                "messages": [
                    ToolMessage(
                        content=f"Error creating profile: {e}",
                        tool_call_id="save_client_profile",
                    )
                ],
            },
            goto="analyze_and_save",
        )
    finally:
        session.close()


@tool
def save_demographic_targets(
    profile_id: int,
    targets: list[dict],
) -> Command[Literal["analyze_and_save"]]:
    """Save demographic targeting criteria for a client profile.

    Args:
        profile_id: The ID of the client profile to add targets to
        targets: List of demographic target dictionaries, each containing:
            - demographic_key: "income", "age", "home_ownership", or "education"
            - constraint_type: "range", "threshold_min", "threshold_max", or "percentage"
            - min_value: For range/threshold_min constraints
            - max_value: For range/threshold_max constraints
            - target_percentage: For percentage constraints (0.0-1.0)
            - percentage_operator: For percentage constraints ("gt", "lt", "gte", "lte", "eq")
            - importance_weight: 0.0-1.0 scale for importance

    Returns:
        Command confirming targets saved
    """
    session = SessionLocal()
    try:
        created_targets = []
        for target_data in targets:
            target = DemographicTarget(
                client_profile_id=profile_id,
                demographic_key=target_data["demographic_key"],
                constraint_type=target_data.get("constraint_type", "range"),
                min_value=target_data.get("min_value"),
                max_value=target_data.get("max_value"),
                target_percentage=target_data.get("target_percentage"),
                percentage_operator=target_data.get("percentage_operator"),
                importance_weight=target_data.get("importance_weight", 0.5),
            )
            session.add(target)
            created_targets.append(target)

        session.commit()

        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"Successfully saved {len(created_targets)} demographic targets for profile {profile_id}",
                        tool_call_id="save_demographic_targets",
                    )
                ],
            },
            goto="analyze_and_save",
        )
    except Exception as e:
        session.rollback()
        return Command(
            update={
                "error": str(e),
                "messages": [
                    ToolMessage(
                        content=f"Error saving demographic targets: {e}",
                        tool_call_id="save_demographic_targets",
                    )
                ],
            },
            goto="analyze_and_save",
        )
    finally:
        session.close()


# Export tools list for binding to LLM
profile_builder_tools = [save_client_profile, save_demographic_targets]
