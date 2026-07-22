# Repository Strip-Down Summary

## What Changed

The Prospector repository has been reduced from a complex multi-agent stack to a clean, minimal setup:

### Removed
- **Old orchestrator agent** (`src/agents/orchestrator/`) — complex state machine with discovery, profiling, and demographic targeting
- **SQL analyst sub-agent** (`src/agents/sql_analyst/`) — report generation pipeline with multiple LLM calls and structured output
- **Agent-specific schemas** — `src/schemas/report.py`, `src/schemas/charts.py`
- **Agent-specific models** — `src/core/state.py` (ClientProfileRef/DemographicTargetRef), `src/core/database/models/client_profile.py` (ClientProfile/DemographicTarget)
- **Agent-supporting services** — `src/services/` (chart_tools, demographic_queries)
- **Agent test files** — all integration tests for SQL agent/analyst
- **Stale scripts** — run_chat.py, run_orchestrator.py, run_sql_analyst.py, run_user_persona.py (all broken/outdated)
- **Old docs and artifacts** — build_sql_agent.md, system_design.md, graph.png, report outputs, evals/

### Added
- **Skeleton chat agent** (`src/agents/chat/`)
  - `state.py` — minimal `ChatState` with just `messages` (using `add_messages` reducer)
  - `agent.py` — `ChatAgent` class with single-node LangGraph
    - Calls `ChatAnthropic` with no tools or structured output
    - Persists conversations via Postgres `AsyncPostgresSaver` checkpointer
    - Same external API as old orchestrator (`chat()`, `get_history()`) for drop-in route compatibility
- **Shared demographics module** — moved `src/agents/orchestrator/demographics.py` → `src/core/demographics.py` (used by aggregation, demographics routes, schema)

### Kept Unchanged
- **Aggregation API routes** — `/get-aggregation`, `/get-demographic-categories`, `/get-demographic-metrics`
- **Geography routes** — `/get-regions`, `/get-cbsa`, `/get-county`, `/get-zips`
- **Database layer** — `src/core/database/connection.py` with `AsyncSessionLocal`, Postgres checkpointer
- **USZip table** — full census data table for querying
- **Alembic migrations** — root migration preserved; new migration drops ClientProfile/DemographicTarget tables

### Dependencies Removed
- `langchain` (LLM orchestration layer, no longer needed)
- `langchain-openai` (not used in skeleton agent)
- `langchain-core` → kept as a dependency of `langchain-anthropic`
- `google-maps-places`, `usaddress`, `geopy` (places/address lookups, agent-only)
- `jinja2` (templating, was only in old SQL analyst prompts)

### Dependencies Kept
- `langchain-anthropic` (for `ChatAnthropic` in the new agent)
- `langgraph` (for `StateGraph`)
- `langgraph-checkpoint-postgres` (for Postgres checkpointer)
- `sqlalchemy`, `sqlmodel`, `asyncpg`, `psycopg2-binary` (DB layer)
- `fastapi`, `uvicorn` (API server)
- `alembic` (migrations)
- `pydantic`, `pydantic-settings` (schemas, config)
- `pandas` (used by load_uszips.py)

## Archived (Not Deleted)

All old code has been moved to `scratch/legacy_agents/` for future reference:
- Orchestrator agent code
- SQL analyst agent code
- All test files for agents
- Stale scripts (with broken imports, kept for reference)
- Old docs and design notes
- Output artifacts

You can reference this code when rebuilding the real agent (which will eventually bind `get_aggregation` as its one tool).

## Chat Endpoints Now

The `/api/chat/*` endpoints still work but are completely minimal:

- `POST /api/chat/conversations` — start a new conversation, get assistant response
- `POST /api/chat/conversations/{id}/messages` — continue conversation
- `GET /api/chat/conversations/{id}` — fetch full message history
- `GET /api/chat/conversations` — list all conversations

All responses now contain just `messages`, `conversation_id`, and timestamps. No profile data, no reports, no structured data — pure LLM chat backed by Postgres checkpointer for multi-turn persistence.

## Database Changes

New migration `alembic/versions/e5089907aef2_drop_client_profile_tables.py` drops:
- `demographic_targets` table (FK dependency)
- `client_profiles` table

USZip table and checkpointer tables (created by `AsyncPostgresSaver.setup()`) are untouched.

## Testing

Run tests with `just test`. Currently no tests are defined for aggregation (you'll need to write those using the preserved `TestUSZip` fixture in `tests/conftest.py`).

## Next Steps

To rebuild the agent as a real tool-using system:

1. Add `get_aggregation` to the chat agent's tool binding:
   ```python
   self.llm.bind_tools([...])  # or via langgraph.prebuilt.tool_executor
   ```
2. Add nodes for tool calling and tool execution
3. Extend ChatState as needed (context, session data, etc.)
4. Add migration to recreate ClientProfile if rebuilding the profiling flow

The skeleton is ready; the rest is up to you.
