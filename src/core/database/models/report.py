"""Report model for storing generated demographic analysis reports."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class Report(SQLModel, table=True):
    """Persisted demographic analysis report linked to a client profile and conversation."""

    __tablename__ = "reports"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    client_profile_id: str = Field(foreign_key="client_profiles.id", index=True)
    conversation_id: str = Field(max_length=255, index=True)

    title: str
    subtitle: Optional[str] = None
    geography_type: str  # "zip", "county", "state", "cbsa", "region"
    geography_value: str

    # JSONB storage of ReportSummary.model_dump() and list of ReportSection.model_dump()
    # Immutable once created — never queried at field level
    summary: dict = Field(sa_column=Column(JSONB))
    sections: list = Field(sa_column=Column(JSONB))

    generated_at: datetime = Field(sa_column_kwargs={"server_default": func.now()})
