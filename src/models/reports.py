"""Report model for generated location intelligence reports."""

from datetime import datetime

from sqlalchemy import DateTime, Double, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class Report(Base):
    """Generated location intelligence report."""

    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # 'site_selection' | 'trade_area'
    profile_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("client_profiles.id")
    )
    center_lat: Mapped[float | None] = mapped_column(Double)
    center_lng: Mapped[float | None] = mapped_column(Double)
    metro_cbsa: Mapped[str | None] = mapped_column(String(100))
    radius_meters: Mapped[int | None] = mapped_column(Integer)
    html_content: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    report_metadata: Mapped[dict | None] = mapped_column(JSONB)

    # Relationship
    profile = relationship("ClientProfile", backref="reports")
