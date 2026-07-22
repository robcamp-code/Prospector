"""ClientProfile model for customer targeting profiles."""

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import Column, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, Relationship, SQLModel


DEMOGRAPHIC_KEY_MAPPING = {

}


class DemographicTarget(SQLModel, table=True):
    """Target demographic criteria for a client profile.

    Supports multiple constraint types for flexible targeting:
    - range: target values between min_value and max_value
    - threshold_min: target values >= min_value
    - threshold_max: target values <= max_value
    - percentage: target areas meeting percentage criteria
    """

    __tablename__ = "demographic_targets"

    id: Optional[int] = Field(default=None, primary_key=True)
    client_profile_id: str = Field(foreign_key="client_profiles.id", index=True)

    demographic_key: str = Field(max_length=50)  # e.g., "income", "age", "home_ownership"

    # Constraint type: "range", "threshold_min", "threshold_max"
    constraint_type: str = Field(default="range", sa_column=Column(String(20)))

    # Range-based: target income between $50K-$100K
    min_value: Optional[float] = Field(default=None)
    max_value: Optional[float] = Field(default=None)

    # Percentage-based: target areas with >70% homeownership
    target_percentage: Optional[float] = Field(default=None)

    # Operator: "gt", "lt", "gte", "lte", "eq"
    percentage_operator: Optional[str] = Field(default=None, sa_column=Column(String(5)))

    # Weight for scoring (0-1)
    importance_weight: float = Field(default=0.5, ge=0, le=1)

    # Relationship back to profile
    client_profile: Optional["ClientProfile"] = Relationship(back_populates="target_demographics")


class ClientProfile(SQLModel, table=True):
    """Client profile defining ideal customer demographics."""

    __tablename__ = "client_profiles"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    name: str = Field(max_length=255)
    business_type: Optional[str] = Field(default=None, max_length=100)
    service_description: Optional[str] = Field(default=None)

    # Link to conversation (1-to-1)
    conversation_id: Optional[str] = Field(default=None, max_length=255, unique=True, index=True)

    # Relationship to demographic targets
    target_demographics: List[DemographicTarget] = Relationship(
        back_populates="client_profile",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

    # Place types for targeting
    competitor_types: Optional[List[str]] = Field(
        default=None, sa_column=Column(ARRAY(String))
    )
    complimentary_types: Optional[List[str]] = Field(
        default=None, sa_column=Column(ARRAY(String))
    )

    # Timestamps
    created_at: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"server_default": func.now()}
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()},
    )
