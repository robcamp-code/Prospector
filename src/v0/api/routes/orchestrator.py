"""Orchestrator API routes for chat interactions."""

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage
from pydantic import BaseModel

from src.v0.agents.orchestrator import Orchestrator
from src.v0.agents.sql_analyst.models import AnalysisResult
from src.v0.services.analysis_report_service import AnalysisReportService

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""

    message: str
    thread_id: str | None = None


class ChatResponse(BaseModel):
    """Response body for chat endpoint."""

    thread_id: str
    response: str
    profile_id: int | None = None
    has_analysis: bool = False
    html_report: str | None = None


def _extract_response_text(state: dict) -> str:
    """Extract the assistant's response text from state."""
    messages = state.get("messages", [])
    # Find the last AI message
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content
    return ""


def _extract_profile_id(state: dict) -> int | None:
    """Extract profile_id from state if present."""
    client_profile = state.get("client_profile")
    if client_profile is not None:
        if hasattr(client_profile, "profile_id"):
            return client_profile.profile_id
        elif isinstance(client_profile, dict):
            return client_profile.get("profile_id")
    return None


def _has_analysis_result(state: dict) -> bool:
    """Check if state contains an analysis result."""
    return state.get("analysis_result") is not None


def _render_html_report(state: dict) -> str | None:
    """Render HTML report if analysis result exists in state."""
    analysis_result = state.get("analysis_result")
    if analysis_result is None:
        return None

    # Convert dict to AnalysisResult if needed
    if isinstance(analysis_result, dict):
        analysis_result = AnalysisResult(**analysis_result)

    service = AnalysisReportService()
    return service.render_html(analysis_result)


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Process a chat message through the orchestrator.

    Handles both new conversations (thread_id=None) and continuations.

    Args:
        request: Chat request with message and optional thread_id

    Returns:
        ChatResponse with thread_id, response text, and state info
    """
    orchestrator = Orchestrator()

    if request.thread_id is None:
        # New conversation
        result = await orchestrator.run(request.message)
    else:
        # Continue existing conversation
        result = await orchestrator.continue_conversation(
            request.message, request.thread_id
        )

    thread_id = result.get("thread_id", request.thread_id)
    state = result.get("state", {})

    # Handle LangGraph state format - may be wrapped in agent key
    if "agent" in state:
        state = state.get("agent", state)

    response_text = _extract_response_text(state)
    profile_id = _extract_profile_id(state)
    has_analysis = _has_analysis_result(state)
    html_report = _render_html_report(state) if has_analysis else None

    return ChatResponse(
        thread_id=thread_id,
        response=response_text,
        profile_id=profile_id,
        has_analysis=has_analysis,
        html_report=html_report,
    )


async def _stream_chat(
    message: str, thread_id: str | None
) -> AsyncGenerator[str, None]:
    """Generate SSE events for streaming chat response."""
    orchestrator = Orchestrator()

    # For streaming, we need to access the agent directly
    # This is a simplified implementation - full streaming would require
    # deeper integration with LangGraph's streaming capabilities

    try:
        if thread_id is None:
            result = await orchestrator.run(message)
        else:
            result = await orchestrator.continue_conversation(message, thread_id)

        thread_id = result.get("thread_id", thread_id)
        state = result.get("state", {})

        # Handle LangGraph state format
        if "agent" in state:
            state = state.get("agent", state)

        response_text = _extract_response_text(state)
        profile_id = _extract_profile_id(state)
        has_analysis = _has_analysis_result(state)
        html_report = _render_html_report(state) if has_analysis else None

        # Emit message event with the response
        event_data = {
            "type": "message",
            "thread_id": thread_id,
            "content": response_text,
            "profile_id": profile_id,
            "has_analysis": has_analysis,
            "html_report": html_report,
        }
        yield f"data: {json.dumps(event_data)}\n\n"

        # Emit done event
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        error_data = {"type": "error", "message": str(e)}
        yield f"data: {json.dumps(error_data)}\n\n"


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Stream a chat response via Server-Sent Events.

    Args:
        request: Chat request with message and optional thread_id

    Returns:
        StreamingResponse with SSE events: tool_call, message, done
    """
    return StreamingResponse(
        _stream_chat(request.message, request.thread_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
