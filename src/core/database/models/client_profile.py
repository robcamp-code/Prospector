"""ClientProfile model: identity plus a typed preferences JSON blob."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Field, SQLModel


class ClientProfile(SQLModel, table=True):
    """Client profile: who the client is and their extracted preferences.

    ``preferences`` stores a ``src.schemas.preferences.Preferences`` dump.
    Always revalidate through ``load_preferences()`` when reading — rows
    written under an older schema deserialize to None (treated as
    incomplete) instead of crashing a resumed conversation.
    """

    __tablename__ = "client_profiles"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    name: str = Field(max_length=255)
    business_type: Optional[str] = Field(default=None, max_length=100)
    service_description: Optional[str] = Field(default=None)

    # Link to conversation (1-to-1)
    conversation_id: Optional[str] = Field(default=None, max_length=255, unique=True, index=True)

    # Typed preferences (Preferences.model_dump()); source of truth for the agent
    preferences: Optional[dict] = Field(default=None, sa_column=Column(JSONB))

    # Timestamps
    created_at: Optional[datetime] = Field(
        default=None, sa_column_kwargs={"server_default": func.now()}
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column_kwargs={"server_default": func.now(), "onupdate": func.now()},
    )


async def get_profile_by_conversation_id(
    session: AsyncSession, conversation_id: str
) -> Optional[ClientProfile]:
    """Fetch the ClientProfile linked to a conversation, or None if absent."""
    stmt = select(ClientProfile).where(ClientProfile.conversation_id == conversation_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
