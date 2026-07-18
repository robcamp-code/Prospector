"""Place model for cached Google Places API data."""

from datetime import datetime

from sqlalchemy import ARRAY, DateTime, Double, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.v0.models.base import Base


class Place(Base):
    """Cached business data from Google Places API."""

    __tablename__ = "places"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    place_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(255))
    primary_type: Mapped[str | None] = mapped_column(String(100))
    types: Mapped[list[str] | None] = mapped_column(ARRAY(String(100)))
    lat: Mapped[float | None] = mapped_column(Double)
    lng: Mapped[float | None] = mapped_column(Double)
    zip_code: Mapped[str | None] = mapped_column(String(5))
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(50))
    website: Mapped[str | None] = mapped_column(String(500))
    rating: Mapped[float | None] = mapped_column(Double)
    review_count: Mapped[int | None] = mapped_column(Integer)
    cached_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    raw_json: Mapped[dict | None] = mapped_column(JSONB)
