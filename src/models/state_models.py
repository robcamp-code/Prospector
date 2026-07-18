"""Global state models for orchestrator agents."""

from pydantic import BaseModel, Field


class ClientProfileRef(BaseModel):
    """Reference to ClientProfile in database with cached key fields.

    This model stores profile_id plus cached fields (not full SQLAlchemy model) because:
    - SQLAlchemy models don't serialize for LangGraph checkpointing
    - Downstream agents can fetch fresh data from DB when needed
    - Reduces state size
    """

    profile_id: int = Field(description="Database ID of the ClientProfile")
    name: str = Field(description="Business name")
    business_type: str | None = Field(default=None, description="Type of business")
    service_description: str | None = Field(
        default=None, description="Description of services offered"
    )
    competitor_types: list[str] = Field(
        default_factory=list,
        description="Google Places API types for direct competitors",
    )
    complimentary_types: list[str] = Field(
        default_factory=list,
        description="Google Places API types for complementary businesses",
    )
    target_income_min: int | None = Field(
        default=None, description="Minimum target annual household income in USD"
    )
    target_income_max: int | None = Field(
        default=None, description="Maximum target annual household income in USD"
    )
    target_age_min: int | None = Field(
        default=None, description="Minimum target customer age"
    )
    target_age_max: int | None = Field(
        default=None, description="Maximum target customer age"
    )
