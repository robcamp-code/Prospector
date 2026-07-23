"""Request and response schemas for chat endpoints."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class StartConversationRequest(BaseModel):
    """Request to start a new conversation."""

    message: str = Field(..., description="Initial message to start the conversation")
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the conversation was created (defaults to now)",
    )


class SendMessageRequest(BaseModel):
    """Request to send a message in an existing conversation."""

    message: str = Field(..., description="Message to send")


class MessageResponse(BaseModel):
    """A single message in a conversation."""

    role: str = Field(..., description="Role of the message sender (user/assistant)")
    content: str = Field(..., description="Content of the message")


class ConversationResponse(BaseModel):
    """Response containing conversation details."""

    id: str = Field(..., description="Conversation ID (thread_id)")
    messages: list[MessageResponse] = Field(
        default_factory=list, description="List of messages in the conversation"
    )
    created_at: datetime | None = Field(
        default=None, description="When the conversation was created"
    )


class ChatResponse(BaseModel):
    """Response after sending a message."""

    conversation_id: str = Field(..., description="Conversation ID (thread_id)")
    message: MessageResponse = Field(..., description="The assistant's response")
    created_at: datetime | None = Field(
        default=None, description="When the conversation was created"
    )
    report: "Report | None" = Field(
        default=None, description="Demographic report, present once complete"
    )


class ConversationListItem(BaseModel):
    """Summary of a conversation for listing."""

    id: str = Field(..., description="Conversation ID")
    preview: str = Field(..., description="Preview of the last message")
    message_count: int = Field(..., description="Number of messages in conversation")
