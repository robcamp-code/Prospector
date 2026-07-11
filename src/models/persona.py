"""User persona model."""

from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from src.models.enums import (
    ContentCapacity,
    DeliverableVisibility,
    GeographyScope,
    SalesCycle,
    ServiceType,
    SourceType,
    TargetClientSize,
)


class UserPersona(BaseModel):
    """Structured persona used to drive platform scoring, hashtag/target
    generation, and lead relevance scoring downstream."""

    persona_id: Optional[UUID] = Field(default=None)
    name: str = Field(..., description="Short label, e.g. 'Freelance Web/Automation Dev'")

    industry: str = Field(..., description="e.g. 'web development', 'photography'")
    sub_industry: Optional[str] = Field(
        default=None, description="e.g. 'AI agent development', 'wedding photography'"
    )

    service_type: ServiceType
    deliverable_visibility: DeliverableVisibility
    sales_cycle: SalesCycle
    target_client_size: TargetClientSize
    geography_scope: GeographyScope
    content_capacity: ContentCapacity

    services_offered: Optional[list[str]] = Field(
        default=None,
        description="Concrete offerings, e.g. ['LangChain agents', 'FastAPI booking sites']",
    )
    target_client_keywords: Optional[list[str]] = Field(
        default=None,
        description="Roles/industries of the ideal client, used for seeding e.g. ['coach', 'local service business']",
    )

    source_type: SourceType
    raw_input: Optional[str] = Field(
        default=None,
        description="Original questionnaire answers or file-derived text, kept "
        "verbatim for auditability and re-scoring if heuristics change",
    )
    preferred_client_locations: Optional[list[str]] = Field(
        default=None,
        description="list of preferred locations for potential clients i.e (atlanta, georgia)",
    )

    @field_validator("persona_id", mode="before")
    @classmethod
    def convert_to_uuid(cls, v):
        if v is None:
            return uuid4()
        if isinstance(v, UUID):
            return v
        try:
            return UUID(v)
        except (ValueError, AttributeError):
            return uuid4()

    @field_validator("services_offered", mode="before")
    @classmethod
    def default_services_offered(cls, v):
        if v is None:
            return []
        return cls._dedupe_and_strip(v)

    @field_validator("target_client_keywords", mode="before")
    @classmethod
    def default_target_client_keywords(cls, v):
        if v is None:
            return []
        return cls._dedupe_and_strip(v)

    @field_validator("preferred_client_locations", mode="before")
    @classmethod
    def default_preferred_locations(cls, v):
        if v is None:
            return ["Atlanta, Georgia"]
        return v

    @field_validator("raw_input", mode="before")
    @classmethod
    def default_raw_input(cls, v):
        if v is None:
            return ""
        return v

    @staticmethod
    def _dedupe_and_strip(v: list[str]) -> list[str]:
        seen, out = set(), []
        for item in v:
            item = item.strip()
            if item and item.lower() not in seen:
                seen.add(item.lower())
                out.append(item)
        return out

    model_config = {
        "use_enum_values": True,
    }
