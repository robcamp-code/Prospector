"""ClientProfile and DemographicTarget models for storing client business profiles."""

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from sqlalchemy import Column, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import Field, Relationship, SQLModel

from src.core.state import ClientProfileRef, DemographicTargetRef


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

    # Constraint type: "range", "threshold_min", "threshold_max", "percentage"
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
    """Client profile defining ideal customer demographics and business context."""

    __tablename__ = "client_profiles"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    name: str = Field(max_length=255)
    business_type: Optional[str] = Field(default=None, max_length=100)
    service_description: Optional[str] = Field(default=None)

    # Link to conversation (1-to-1)
    conversation_id: Optional[str] = Field(default=None, max_length=255, unique=True, index=True)

    # Relationship to demographic targets.
    # lazy="selectin" eager-loads targets via a second async SELECT as part of
    # the parent query, so client_profile_to_ref() never triggers a sync
    # lazy-load (which raises MissingGreenlet under async SQLAlchemy).
    target_demographics: List[DemographicTarget] = Relationship(
        back_populates="client_profile",
        sa_relationship_kwargs={"cascade": "all, delete-orphan", "lazy": "selectin"},
    )

    # Place types for targeting
    competitor_types: Optional[List[str]] = Field(
        default=None, sa_column=Column(ARRAY(String))
    )
    complimentary_types: Optional[List[str]] = Field(
        default=None, sa_column=Column(ARRAY(String))
    )

    # Income targeting (LLM-extracted, used by Data Analyst to guide report)
    target_income_min: Optional[int] = Field(default=None)
    target_income_max: Optional[int] = Field(default=None)

    # Raw location preference (free text, resolved by Data Analyst)
    location_preference: Optional[str] = Field(default=None)

    # Timestamps
    created_at: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"server_default": func.now()}
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()},
    )


# Converter functions (DRY principle: single place for DB ↔ state ref mapping)


def client_profile_to_ref(profile: ClientProfile) -> ClientProfileRef:
    """Convert DB ClientProfile row to JSON-serializable state ref."""
    return ClientProfileRef(
        profile_id=profile.id,
        name=profile.name,
        business_type=profile.business_type,
        service_description=profile.service_description,
        competitor_types=profile.competitor_types or [],
        complimentary_types=profile.complimentary_types or [],
        target_income_min=profile.target_income_min,
        target_income_max=profile.target_income_max,
        location_preference=profile.location_preference,
        target_demographics=[
            demographic_target_to_ref(t) for t in (profile.target_demographics or [])
        ],
    )


def demographic_target_to_ref(target: DemographicTarget) -> DemographicTargetRef:
    """Convert DB DemographicTarget row to JSON-serializable state ref."""
    return DemographicTargetRef(
        demographic_key=target.demographic_key,
        constraint_type=target.constraint_type,  # type: ignore
        min_value=target.min_value,
        max_value=target.max_value,
        target_percentage=target.target_percentage,
        percentage_operator=target.percentage_operator,  # type: ignore
        importance_weight=target.importance_weight,
    )


def ref_to_client_profile_kwargs(ref: ClientProfileRef) -> dict:
    """Convert state ref to kwargs for creating a ClientProfile DB row."""
    return {
        "name": ref.name or "Unknown",
        "business_type": ref.business_type,
        "service_description": ref.service_description,
        "competitor_types": ref.competitor_types or None,
        "complimentary_types": ref.complimentary_types or None,
        "target_income_min": ref.target_income_min,
        "target_income_max": ref.target_income_max,
        "location_preference": ref.location_preference,
    }
