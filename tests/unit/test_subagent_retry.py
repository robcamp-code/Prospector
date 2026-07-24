"""Tests for SubAgent.ainvoke_with_retry: retrying transient Anthropic API errors.

Regression: the `follow_up` node crashed the whole graph run on
`anthropic.APIStatusError: overloaded_error`. That error arrives as an SSE
`error` event after streaming has already started with a 200 response, which
bypasses the Anthropic SDK's own HTTP-level retry logic (it only inspects the
initial response status code) -- so retries have to happen in application code.
"""

from unittest.mock import AsyncMock

import anthropic
import httpx
import pytest

from src.agents.chat.base import SubAgent


class _DummyAgent(SubAgent):
    async def __call__(self, state, config):
        raise NotImplementedError


def _overloaded_error() -> anthropic.APIStatusError:
    response = httpx.Response(200, request=httpx.Request("POST", "https://api.anthropic.com"))
    return anthropic.APIStatusError(
        "overloaded_error",
        response=response,
        body={"type": "error", "error": {"type": "overloaded_error", "message": "Overloaded"}},
    )


@pytest.fixture
def agent(monkeypatch):
    monkeypatch.setattr(SubAgent, "__init__", lambda self: None)
    monkeypatch.setattr("src.agents.chat.base.asyncio.sleep", AsyncMock())
    return _DummyAgent()


@pytest.mark.asyncio
async def test_retries_then_succeeds(agent):
    runnable = AsyncMock()
    runnable.ainvoke.side_effect = [_overloaded_error(), "ok"]

    result = await agent.ainvoke_with_retry(runnable, ["message"], retries=2)

    assert result == "ok"
    assert runnable.ainvoke.call_count == 2


@pytest.mark.asyncio
async def test_raises_after_exhausting_retries(agent):
    runnable = AsyncMock()
    runnable.ainvoke.side_effect = [_overloaded_error(), _overloaded_error(), _overloaded_error()]

    with pytest.raises(anthropic.APIStatusError):
        await agent.ainvoke_with_retry(runnable, ["message"], retries=2)

    assert runnable.ainvoke.call_count == 3


@pytest.mark.asyncio
async def test_does_not_retry_other_exceptions(agent):
    runnable = AsyncMock()
    runnable.ainvoke.side_effect = ValueError("not a transient API error")

    with pytest.raises(ValueError):
        await agent.ainvoke_with_retry(runnable, ["message"], retries=2)

    assert runnable.ainvoke.call_count == 1
