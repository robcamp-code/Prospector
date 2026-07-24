"""Live end-to-end chat API test: real app, real LLM, real database. No mocking.

Simulates exactly what a client does: start a conversation, then continue it.
The continue call is the resume path that has broken twice (duplicate
ClientProfile insert; dangling tool_use blocks in checkpointed history).

Also the regression harness for the east-coast scoping bug: a Northeast
request must never surface West/South-reference states (California, Texas,
Oregon, Washington) in the generated report.

Slow (~2-3 min) and spends real tokens: excluded from `just test`,
run via `just test-live`.
"""

import asyncio
import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from src.api.main import app
from src.core.database import (
    AsyncSessionLocal,
    Report,
    async_engine,
    get_profile_by_conversation_id,
)

PROFILE_MESSAGE = (
    "Hi! My business is called LiveTest Tutors {nonce}. It is an education business "
    "offering math tutoring for high schoolers, priced around $80 per session. "
    "My target customers are college-educated families with above-average income. "
    "I am open to anywhere in the Northeast near a major city. "
    "Demographics I care about: education, income, age."
)

FOLLOW_UP_MESSAGE = (
    "One update: my price point is actually $95 per session, and please emphasize "
    "areas with strong college education rates."
)

# States that can only appear if the location filter was dropped (the original
# bug pulled California and Texas into an "east coast" report). "Washington"
# is deliberately excluded: several east-coast states have a Washington County.
OUT_OF_SCOPE_STATES = ["California", "Texas", "Oregon", "Arizona"]


async def _fetch_report(conversation_id: str) -> Report | None:
    async with AsyncSessionLocal() as session:
        report = await session.scalar(
            select(Report).where(Report.conversation_id == conversation_id)
        )
    # Dispose so the next asyncio.run() gets a pool bound to its own loop
    await async_engine.dispose()
    return report


async def _cleanup(conversation_id: str) -> None:
    async with AsyncSessionLocal() as session:
        await session.execute(
            delete(Report).where(Report.conversation_id == conversation_id)
        )
        profile = await get_profile_by_conversation_id(session, conversation_id)
        if profile is not None:
            await session.delete(profile)
        await session.commit()
    await async_engine.dispose()


def _assert_report_in_scope(body: dict) -> None:
    """The report must have real content and stay inside the requested scope."""
    report = body.get("report")
    assert report, "profile message was complete; a report should be generated"

    sections = report.get("sections") or []
    assert sections, "report must have sections"

    report_text = json.dumps(report)
    for state_name in OUT_OF_SCOPE_STATES:
        assert state_name not in report_text, (
            f"'{state_name}' appeared in a Northeast-scoped report — "
            "location WHERE filter was dropped"
        )

    # The client's focus categories must actually carry data (the original bug
    # produced empty 'data pending' education sections).
    assert "education" in report_text or "income" in report_text


@pytest.mark.live
def test_start_and_continue_conversation():
    conversation_id = None
    try:
        # TestClient as context manager runs the app lifespan (DB + checkpointer init)
        with TestClient(app) as client:
            response = client.post(
                "/api/chat/conversations",
                json={"message": PROFILE_MESSAGE.format(nonce=uuid4().hex[:8])},
            )
            assert response.status_code == 200, response.text
            body = response.json()
            conversation_id = body["conversation_id"]
            assert conversation_id
            _assert_report_in_scope(body)

            # The resume path: this exact call 500'd before the fixes
            response = client.post(
                f"/api/chat/conversations/{conversation_id}/messages",
                json={"message": FOLLOW_UP_MESSAGE},
            )
            assert response.status_code == 200, response.text
            body = response.json()
            assert body["conversation_id"] == conversation_id
            _assert_report_in_scope(body)

        # Persisted report row reflects the scoped run
        db_report = asyncio.run(_fetch_report(conversation_id))
        assert db_report is not None
        assert db_report.sections, "persisted report must have sections"
        persisted_text = json.dumps(db_report.sections)
        for state_name in OUT_OF_SCOPE_STATES:
            assert state_name not in persisted_text
    finally:
        # Runs after lifespan shutdown (engine disposed); a fresh event loop
        # gives the engine a new pool for the cleanup queries.
        if conversation_id:
            asyncio.run(_cleanup(conversation_id))
