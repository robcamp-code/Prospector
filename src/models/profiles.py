"""ClientProfile model for customer targeting profiles."""

from datetime import datetime

from sqlalchemy import DateTime, Double, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.models.base import Base


class ClientProfile(Base):
    """Client profile defining ideal customer demographics."""

    __tablename__ = "client_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_type: Mapped[str | None] = mapped_column(String(100))
    service_description: Mapped[str | None] = mapped_column(Text)

    # Ideal Customer
    target_income_min: Mapped[int | None] = mapped_column(Integer)
    target_income_max: Mapped[int | None] = mapped_column(Integer)
    target_age_min: Mapped[int | None] = mapped_column(Integer)
    target_age_max: Mapped[int | None] = mapped_column(Integer)
    target_home_ownership_min: Mapped[float | None] = mapped_column(Double)
    target_education_min: Mapped[float | None] = mapped_column(Double)

    # Place types for targeting
    competitor_types: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    complimentary_types: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    # Custom scoring weights
    custom_weights: Mapped[dict | None] = mapped_column(JSONB)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
