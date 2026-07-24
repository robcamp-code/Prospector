# Prospector - Development Notes

## Agent conventions

- `SubAgent` (ABC in `src/agents/chat/base.py`) is the base class for every
  LLM-backed LangGraph node. Non-LLM nodes (e.g. `done_message`) are plain
  callables and don't subclass it.
- Each subagent lives in its own package under `src/agents/chat/`:
  `node.py` plus `prompts.py` (and `templates.py` / `sql.py` as needed).
- All prompts and formatted strings live in `prompts.py` / `templates.py` /
  `sql.py` and are `.format()`-ed in logic code — never inline string
  literals inside node code.
- State discipline: only JSON-serializable dicts cross node boundaries.
  Typed models (`Preferences`, `QueryPlan`) are stored as `model_dump()` and
  revalidated at each node boundary (`load_preferences`,
  `QueryPlan.model_validate`). `load_preferences` returns `None` on schema
  drift so resumed conversations re-extract instead of crashing.
- Location preferences only ever become WHERE-clause filters
  (`LocationPreference.filter_kwargs()` → `get_aggregation`), never GROUP BY
  choices. `AggregationQuery` has no location fields by design — keep it
  that way.

## Verification (required — do not claim a fix without it)

Every change must be verified by actually exercising the affected flow, not just
by unit tests or reasoning about the code. Two mechanisms, both must be runnable
by a human with a single command:

- `just test` — fast suite, no external APIs. Run after every change.
- `just test-live` — end-to-end chat flow through the real API
  (`tests/integration/test_chat_api_live.py`: FastAPI TestClient, **no mocking**,
  real LLM + Postgres, ~2-3 min, costs tokens). **Required before claiming any
  fix that touches `src/agents/chat/` or the chat API routes.** It starts a
  conversation and then continues it — the resume path is where multiple bugs
  have hidden (duplicate ClientProfile insert, dangling tool_use blocks).

Conventions:

- Every bug fix ships with a regression test that reproduces the original failure.
- API behavior is verified with the live test client against the real app, not mocks.
- Workflows a human will run repeatedly (e.g. upcoming evals) get a `just` recipe
  (e.g. `just evals`) rather than only a pytest test. Prefer adding a recipe over
  documenting a manual command sequence.
- Track newly discovered problems in `Issues.md` (root): Open/Resolved sections
  with symptom, root cause, and fix.

## Known Issues & Patterns

### SQLAlchemy DetachedInstanceError with LangGraph

When passing SQLAlchemy ORM objects through LangGraph state between nodes, you may encounter `DetachedInstanceError` when accessing model attributes after the session is closed.

**Root Cause**: By default, SQLAlchemy expires all attributes after `session.commit()`. When the session closes and later code tries to access those attributes, SQLAlchemy attempts to lazy-load them from the database, but the session is gone.

**Solution**: Use `expire_on_commit=False` in the session factory configuration:

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,  # Prevents DetachedInstanceError
)
```

This is configured in `src/core/database.py`. When wiring up API routes, ensure you use `AsyncSessionLocal` (or the `get_db` dependency) rather than creating raw `AsyncSession(engine)` instances.

**Affected Files**:
- `src/core/database.py` - Session factory configuration
- `src/agents/orchestrator/agent.py` - Uses sessions for persisting ClientProfile
