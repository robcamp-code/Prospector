"""CRM row model for lead storage."""

from datetime import datetime, timezone
from typing import Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


class CRMRow(BaseModel):
    """A single lead entry in the CRM."""

    lead_id: Optional[UUID] = Field(default=None)

    # Contact Info
    name: str
    headline: str | None = None
    bio: str | None = None

    # Platform Links (removed linkedin_url, added youtube/maps)
    instagram_url: str | None = None
    youtube_url: str | None = None
    google_maps_url: str | None = None
    website: str | None = None

    # Engagement Signals
    follower_count: int | None = None
    is_business_account: bool = False

    # Google Maps specific fields
    rating: float | None = None
    review_count: int | None = None
    phone: str | None = None

    # Company Info (if B2B lead)
    company_name: str | None = None
    company_size: str | None = None
    company_industry: str | None = None

    # Location
    location: str | None = None

    # Source & Scoring
    source: Literal["instagram", "youtube", "google_maps"]
    discovered_via_keyword: str | None = None
    created_at: Optional[datetime] = Field(default=None)

    @field_validator("lead_id", mode="before")
    @classmethod
    def convert_lead_id_to_uuid(cls, v):
        if v is None:
            return uuid4()
        if isinstance(v, UUID):
            return v
        try:
            return UUID(v)
        except (ValueError, AttributeError):
            return uuid4()

    @field_validator("created_at", mode="before")
    @classmethod
    def set_created_at(cls, v):
        if v is None:
            return datetime.now(timezone.utc)
        return v
