"""Tools for the User Persona Agent."""

from typing import Annotated

from langchain_core.tools import tool, InjectedToolCallId
from langchain_core.messages import ToolMessage
from langgraph.types import Command
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.v0.agents.user_persona.prompts import VALID_PLACE_TYPES
from src.v0.models.base import SessionLocal
from src.v0.models.profiles import ClientProfile


class IdealCustomerInput(BaseModel):
    """Input schema for analyzing ideal customer demographics."""

    business_name: str = Field(description="Name of the business")
    business_type: str = Field(description="Type/category of business")
    service_description: str = Field(
        description="Detailed description of services offered"
    )


class IdealCustomerOutput(BaseModel):
    """Output schema for ideal customer demographics."""

    target_income_min: int = Field(
        description="Minimum target annual household income in USD"
    )
    target_income_max: int = Field(
        description="Maximum target annual household income in USD"
    )
    target_age_min: int = Field(description="Minimum target customer age")
    target_age_max: int = Field(description="Maximum target customer age")
    target_home_ownership_min: float = Field(
        ge=0.0, le=1.0, description="Minimum home ownership rate (0.0-1.0)"
    )
    target_education_min: float = Field(
        ge=0.0, le=1.0, description="Minimum education level (0.0-1.0)"
    )
    reasoning: str = Field(
        description="Explanation for the demographic choices"
    )


class PlaceTypesInput(BaseModel):
    """Input schema for identifying place types."""

    service_description: str = Field(
        description="Description of the business and its services"
    )


class PlaceTypesOutput(BaseModel):
    """Output schema for competitor and complementary place types."""

    competitor_types: list[str] = Field(
        description="3-7 Google Places API types for direct competitors"
    )
    complementary_types: list[str] = Field(
        description="3-7 Google Places API types for complementary businesses"
    )
    reasoning: str = Field(
        description="Explanation for the place type selections"
    )


class ClientProfileInput(BaseModel):
    """Input schema for creating a client profile."""

    name: str = Field(description="Name of the client/business profile")
    business_type: str = Field(description="Type/category of business")
    service_description: str = Field(description="Description of services offered")
    target_income_min: int = Field(description="Minimum target annual household income")
    target_income_max: int = Field(description="Maximum target annual household income")
    target_age_min: int = Field(description="Minimum target customer age")
    target_age_max: int = Field(description="Maximum target customer age")
    target_home_ownership_min: float = Field(
        ge=0.0, le=1.0, description="Minimum home ownership rate"
    )
    target_education_min: float = Field(
        ge=0.0, le=1.0, description="Minimum education level"
    )
    competitor_types: list[str] = Field(description="Competitor place types")
    complementary_types: list[str] = Field(description="Complementary place types")
    custom_weights: dict | None = Field(
        default=None, description="Optional custom scoring weights"
    )


class ClientProfileOutput(BaseModel):
    """Output schema for saved client profile."""

    id: int = Field(description="Database ID of the created profile")
    name: str = Field(description="Name of the profile")
    success: bool = Field(description="Whether the profile was saved successfully")
    message: str = Field(description="Status message")


def validate_place_types(types: list[str]) -> list[str]:
    """Validate and filter place types against the allowed list."""
    return [t for t in types if t in VALID_PLACE_TYPES]


@tool
def save_client_profile(
    name: Annotated[str, "Name of the client/business profile"],
    business_type: Annotated[str, "Type/category of business"],
    service_description: Annotated[str, "Description of services offered"],
    target_income_min: Annotated[int, "Minimum target annual household income"],
    target_income_max: Annotated[int, "Maximum target annual household income"],
    target_age_min: Annotated[int, "Minimum target customer age"],
    target_age_max: Annotated[int, "Maximum target customer age"],
    target_home_ownership_min: Annotated[float, "Minimum home ownership rate (0.0-1.0)"],
    target_education_min: Annotated[float, "Minimum education level (0.0-1.0)"],
    competitor_types: Annotated[list[str], "List of competitor Google Places API types"],
    complementary_types: Annotated[list[str], "List of complementary Google Places API types"],
    custom_weights: Annotated[dict | None, "Optional custom scoring weights"] = None,
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> Command:
    """Save a complete ClientProfile to the database.

    This tool creates a new ClientProfile record with all the ideal customer
    demographics and place type mappings. Use this after analyzing the business
    and determining all profile fields.
    """
    print("=" * 60)
    print("SAVE_CLIENT_PROFILE TOOL CALLED")
    print("=" * 60)
    print(f"  name: {name}")
    print(f"  business_type: {business_type}")
    print(f"  service_description: {service_description[:50]}...")
    print(f"  target_income_min: {target_income_min}")
    print(f"  target_income_max: {target_income_max}")
    print(f"  target_age_min: {target_age_min}")
    print(f"  target_age_max: {target_age_max}")
    print(f"  target_home_ownership_min: {target_home_ownership_min}")
    print(f"  target_education_min: {target_education_min}")
    print(f"  competitor_types: {competitor_types}")
    print(f"  complementary_types: {complementary_types}")
    print(f"  custom_weights: {custom_weights}")

    # Validate place types
    valid_competitor_types = validate_place_types(competitor_types)
    valid_complementary_types = validate_place_types(complementary_types)
    print(f"  valid_competitor_types after filtering: {valid_competitor_types}")
    print(f"  valid_complementary_types after filtering: {valid_complementary_types}")

    if not valid_competitor_types:
        print("WARNING: no competitor types found after validation")
        valid_competitor_types = []
    if not valid_complementary_types:
        print("WARNING: no complementary types found after validation")
        valid_complementary_types = []

    # Create session directly - FastAPI Depends() doesn't work with LangChain tools
    print("Creating database session...")
    session: Session = SessionLocal()
    print(f"Session created: {session}")
    print(f"Session bind: {session.bind}")

    try:
        print("Creating ClientProfile object...")
        profile = ClientProfile(
            name=name,
            business_type=business_type,
            service_description=service_description,
            target_income_min=target_income_min,
            target_income_max=target_income_max,
            target_age_min=target_age_min,
            target_age_max=target_age_max,
            target_home_ownership_min=target_home_ownership_min,
            target_education_min=target_education_min,
            competitor_types=valid_competitor_types,
            complimentary_types=valid_complementary_types,
            custom_weights=custom_weights,
        )
        print(f"ClientProfile object created: {profile}")
        print(f"  profile.name: {profile.name}")
        print(f"  profile.id (before add): {profile.id}")

        print("Adding profile to session...")
        session.add(profile)
        print("Profile added to session")

        print("Committing session...")
        session.commit()
        print("Session committed successfully!")

        print("Refreshing profile from database...")
        session.refresh(profile)
        print(f"Profile refreshed, ID: {profile.id}")

        print("=" * 60)
        print(f"SUCCESS: Created ClientProfile with ID {profile.id}")
        print(f"  business_type: {profile.business_type}")
        print(f"  competitor_types: {profile.competitor_types}")
        print(f"  complimentary_types: {profile.complimentary_types}")
        print("=" * 60)

        success_message = f"Successfully created ClientProfile with ID {profile.id}"

        return Command(
            update={
                "profile_id": profile.id,
                "messages": [ToolMessage(content=success_message, tool_call_id=tool_call_id)],
            }
        )
    except Exception as e:
        print("=" * 60)
        print(f"ERROR: Failed to save profile: {e}")
        print(f"Exception type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        print("=" * 60)
        session.rollback()
        print("Session rolled back")

        error_message = f"Failed to save profile: {str(e)}"

        return Command(
            update={
                "messages": [ToolMessage(content=error_message, tool_call_id=tool_call_id)],
            }
        )
    finally:
        print("Closing session...")
        session.close()
        print("Session closed")


# List of all tools available to the agent
TOOLS = [save_client_profile]
