"""Chat API routes for conversation management."""

from fastapi import APIRouter, HTTPException
from langchain_core.messages import AIMessage, HumanMessage

from src.agents.chat import ChatAgent
from src.schemas.chat import (
    ChatResponse,
    ConversationListItem,
    ConversationResponse,
    MessageResponse,
    SendMessageRequest,
    StartConversationRequest,
)

router = APIRouter(prefix="/chat", tags=["chat"])


def _message_to_response(msg) -> MessageResponse:
    """Convert a LangChain message to a MessageResponse."""
    if isinstance(msg, HumanMessage):
        role = "user"
    elif isinstance(msg, AIMessage):
        role = "assistant"
    else:
        role = "system"

    content = msg.content if hasattr(msg, "content") else str(msg)
    return MessageResponse(role=role, content=content)


def _extract_assistant_response(state: dict) -> str:
    """Extract the assistant's response text from state."""
    messages = state.get("messages", [])
    # Find the last AI message
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content
    return ""


def _build_chat_response(
    conversation_id: str, state: dict, created_at=None
) -> ChatResponse:
    """Build a ChatResponse from the chat agent's state."""
    response_text = _extract_assistant_response(state)

    return ChatResponse(
        conversation_id=conversation_id,
        message=MessageResponse(role="assistant", content=response_text),
        created_at=created_at,
    )


@router.post("/conversations", response_model=ChatResponse)
async def start_conversation(request: StartConversationRequest) -> ChatResponse:
    """Start a new conversation.

    Creates a new conversation thread and sends the initial message.

    Args:
        request: Request containing the initial message

    Returns:
        ChatResponse with conversation_id and assistant's response
    """
    agent = ChatAgent()
    result = await agent.chat(request.message)

    return _build_chat_response(
        result["thread_id"], result.get("state", {}), created_at=request.created_at
    )


@router.post("/conversations/{conversation_id}/messages", response_model=ChatResponse)
async def send_message(
    conversation_id: str, request: SendMessageRequest
) -> ChatResponse:
    """Send a message in an existing conversation.

    Args:
        conversation_id: The conversation thread ID
        request: Request containing the message to send

    Returns:
        ChatResponse with conversation_id and assistant's response
    """
    agent = ChatAgent()
    result = await agent.chat(request.message, thread_id=conversation_id)

    return _build_chat_response(conversation_id, result.get("state", {}))


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
) -> ConversationResponse:
    """Get conversation history.

    Args:
        conversation_id: The conversation thread ID

    Returns:
        ConversationResponse with full message history
    """
    agent = ChatAgent()
    messages = await agent.get_history(conversation_id)

    if not messages:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Filter out system messages for the response
    message_responses = [
        _message_to_response(msg)
        for msg in messages
        if isinstance(msg, (HumanMessage, AIMessage))
    ]

    return ConversationResponse(
        id=conversation_id,
        messages=message_responses,
    )


@router.get("/conversations")
async def list_conversations():
    """List all conversations.

    Returns:
        List of conversation summaries with id, preview, and message count
    """
    from src.core.database import get_checkpointer

    checkpointer = get_checkpointer()

    # Get all checkpoints, group by thread_id (take latest per thread)
    conversations = {}
    async for checkpoint_tuple in checkpointer.alist(None):
        thread_id = checkpoint_tuple.config["configurable"]["thread_id"]

        # Only keep the first (latest) checkpoint per thread
        if thread_id in conversations:
            continue

        # Extract messages from checkpoint
        checkpoint = checkpoint_tuple.checkpoint
        channel_values = checkpoint.get("channel_values", {})
        messages = channel_values.get("messages", [])

        # Build preview from last message
        preview = ""
        if messages:
            last_msg = messages[-1]
            content = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
            preview = content[:100] + "..." if len(content) > 100 else content

        conversations[thread_id] = ConversationListItem(
            id=thread_id,
            preview=preview,
            message_count=len(messages),
        )

    return {"conversations": list(conversations.values())}
