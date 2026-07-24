"""Regression test: ProfileBuilder must update, not duplicate, a profile on resumed conversations.

Runs against the real database (requires .env, so run via `just test`).
"""

from uuid import uuid4

import pytest
from langchain_core.messages import HumanMessage
from sqlalchemy import func, select

from src.agents.chat.profile_builder.node import ProfileBuilder
from src.core.database import AsyncSessionLocal, ClientProfile, async_engine
from src.schemas.preferences import LocationPreference, Preferences, load_preferences


class _FakeStructuredLLM:
    def __init__(self, preferences: Preferences):
        self._preferences = preferences

    async def ainvoke(self, _messages):
        return self._preferences


class _FakeLLM:
    def __init__(self, preferences: Preferences):
        self._preferences = preferences

    def with_structured_output(self, _schema):
        return _FakeStructuredLLM(self._preferences)


def _make_builder(preferences: Preferences) -> ProfileBuilder:
    # Bypass __init__ to avoid constructing a real ChatAnthropic client.
    builder = ProfileBuilder.__new__(ProfileBuilder)
    builder.llm = _FakeLLM(preferences)
    return builder


def _complete_preferences(name: str) -> Preferences:
    return Preferences(
        name=name,
        business_type="Education",
        service_description="Language tutoring",
        price_point="$50/hr",
        target_customer_description="Bilingual families",
        location=LocationPreference(region="east_coast", area_type="urban"),
        demographic_categories=["language", "education"],
    )


@pytest.mark.asyncio
async def test_profile_builder_updates_existing_profile_on_resume():
    thread_id = f"test-upsert-{uuid4()}"
    state = {
        "messages": [HumanMessage(content="hi")],
        "preferences": None,
        "profile_complete": False,
    }
    config = {"configurable": {"thread_id": thread_id}}

    try:
        result_one = await _make_builder(_complete_preferences("First Name"))(state, config)
        assert result_one["profile_complete"] is True
        assert result_one["profile_id"]

        # Second run with the same thread_id must update, not raise IntegrityError.
        result_two = await _make_builder(_complete_preferences("Updated Name"))(state, config)
        assert result_two["profile_complete"] is True
        assert result_two["profile_id"] == result_one["profile_id"]

        async with AsyncSessionLocal() as session:
            count = await session.scalar(
                select(func.count())
                .select_from(ClientProfile)
                .where(ClientProfile.conversation_id == thread_id)
            )
            assert count == 1

            row = await session.scalar(
                select(ClientProfile).where(ClientProfile.conversation_id == thread_id)
            )
            assert row.name == "Updated Name"

            # Stored preferences must round-trip through the safe loader
            stored = load_preferences(row.preferences)
            assert stored is not None
            assert stored.location.region == "east_coast"
            assert stored.is_complete()
    finally:
        async with AsyncSessionLocal() as session:
            row = await session.scalar(
                select(ClientProfile).where(ClientProfile.conversation_id == thread_id)
            )
            if row is not None:
                await session.delete(row)
                await session.commit()
        await async_engine.dispose()
