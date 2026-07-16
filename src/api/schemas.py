"""Pydantic schemas for API request/response models."""

from datetime import datetime

from pydantic import BaseModel, Field


# Profile schemas
class ProfileBase(BaseModel):
    """Base profile fields."""

    name: str
    business_type: str | None = None
    service_description: str | None = None
    target_income_min: int | None = None
    target_income_max: int | None = None
    target_age_min: int | None = None
    target_age_max: int | None = None
    target_home_ownership_min: float | None = None
    target_education_min: float | None = None
    custom_weights: dict | None = None


class ProfileCreate(ProfileBase):
    """Schema for creating a profile."""

    pass


class ProfileUpdate(BaseModel):
    """Schema for updating a profile."""

    name: str | None = None
    business_type: str | None = None
    service_description: str | None = None
    target_income_min: int | None = None
    target_income_max: int | None = None
    target_age_min: int | None = None
    target_age_max: int | None = None
    target_home_ownership_min: float | None = None
    target_education_min: float | None = None
    custom_weights: dict | None = None


class ProfileResponse(ProfileBase):
    """Schema for profile response."""

    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Report schemas
class SiteSelectionRequest(BaseModel):
    """Request to generate a site selection report."""

    profile_id: int
    cbsa_name: str


class TradeAreaRequest(BaseModel):
    """Request to generate a trade area report."""

    profile_id: int | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    radius_m: int = Field(default=5000, ge=100, le=50000)


class ReportResponse(BaseModel):
    """Schema for report response."""

    id: int
    report_type: str
    profile_id: int | None
    center_lat: float | None
    center_lng: float | None
    metro_cbsa: str | None
    radius_meters: int | None
    created_at: datetime
    report_metadata: dict | None

    class Config:
        from_attributes = True


class ReportWithHtmlResponse(ReportResponse):
    """Schema for report response including HTML content."""

    html_content: str | None


# ZIP schemas
class ZipSearchResponse(BaseModel):
    """Schema for ZIP/CBSA search results."""

    cbsa_names: list[str]


class ZipNearbyResponse(BaseModel):
    """Schema for nearby ZIP codes."""

    zip: str
    city: str | None
    state_id: str | None
    population: float | None
    income_household_median: float | None

    class Config:
        from_attributes = True


class ZipNearbyListResponse(BaseModel):
    """Schema for list of nearby ZIP codes."""

    zips: list[ZipNearbyResponse]
    count: int
