"""API result models for various platforms."""

from pydantic import BaseModel, Field


class InstagramProfileResult(BaseModel):
    """Filtered Instagram profile data for CRM."""

    name: str = Field(default="", alias="fullName")
    username: str = ""
    bio: str | None = Field(default=None, alias="biography")
    instagram_url: str | None = Field(default=None, alias="url")
    follower_count: int | None = Field(default=None, alias="followersCount")
    is_business_account: bool = Field(default=False, alias="isBusinessAccount")
    website: str | None = Field(default=None, alias="externalUrl")

    model_config = {"extra": "ignore"}


class YouTubeResult(BaseModel):
    """YouTube channel/video result for CRM."""

    title: str = ""
    channel_name: str = ""
    channel_url: str | None = None
    video_url: str | None = None
    subscriber_count: int | None = None
    view_count: int | None = None
    description: str | None = None

    model_config = {"extra": "ignore"}


class GoogleMapsResult(BaseModel):
    """Google Maps business result for CRM."""

    name: str = ""
    address: str | None = None
    phone: str | None = None
    website: str | None = None
    google_maps_url: str | None = None
    rating: float | None = None
    review_count: int | None = None
    business_type: str | None = None

    model_config = {"extra": "ignore"}
