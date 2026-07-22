# Prospector

An AI-powered agent system for analyzing business demographics and market data. Uses LangGraph to orchestrate multi-turn conversations with specialized SQL and research agents.

## Tech Stack

- **Backend**: FastAPI + SQLAlchemy ORM
- **Database**: PostgreSQL (local), Neon (prod)
- **Deployment**: Vercel
- **Package Management**: `uv`
- **Task Automation**: `just`
- **Testing**: pytest
- **LLM Orchestration**: LangGraph
- **API Clients**: OpenAI, Tavily, Anthropic

## Installation & Setup

### Prerequisites

1. **Python 3.11+** with `uv` installed:
   ```bash
   curl https://astral.sh/uv/install.sh | sh
   ```

2. **PostgreSQL 15+** running locally:
   ```bash
   brew install postgresql@15
   brew services start postgresql@15
   createdb aiyana
   ```

3. **Just** (command runner):
   ```bash
   brew install just
   ```

### Initial Setup

1. Clone the repository and enter the directory
2. Copy `.env.example` to `.env` and fill in your API keys
3. Run the setup recipe:
   ```bash
   just setup
   ```

This installs dependencies, runs database migrations, and loads required data.

## Just Recipes

### Development Server

```bash
just dev          # Start uvicorn development server on port 8000
just docs         # Open API documentation in browser
```

### Database

```bash
just migrate            # Run pending Alembic migrations
just migration "name"   # Create a new auto-generated migration
just db-reset           # Drop all tables and recreate (⚠️ destroys data)
just load-zips          # Load US ZIP code data from CSV
```

### Chat & Agent

```bash
just chat                       # Start interactive chat with agent
just chat-continue <id>         # Resume a previous conversation
just chat-message "<message>"   # Send single message to agent
just orchestrator               # Run the orchestrator agent
```

### Testing

**Unit Tests:**
```bash
just test              # Run all tests with verbose output
just test-cov          # Run tests with coverage report
```

**SQL Analyst Integration Tests (requires live database):**
```bash
just test-sql                      # Run all SQL analyst tests
just test-sql-query "<pattern>"    # Run tests matching pattern
just test-sql-list                 # List available test names
```

**SQL Agent Integration Tests:**
```bash
just test-sql-agent                    # Run full SQL Agent tests
just test-sql-agent-unit               # Run unit tests only (fast, no DB)
just test-sql-agent-query "<pattern>"  # Run tests matching pattern
```

### Evaluation

```bash
just eval              # Run full evaluation (resumes from existing results)
just eval-one <id>     # Evaluate single business (re-run)
just eval-force        # Re-run entire dataset, ignoring existing results
```

The evaluation suite generates performance metrics and summary statistics for the agent across all test cases.

### Code Quality

```bash
just lint    # Check code with ruff
just fmt     # Format code with ruff
```

## Environment Variables

See `.env.example` for required configuration. Key variables:

- **LLM APIs**: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`
- **Database**: `DATABASE_URL` (PostgreSQL connection string)
- **Logging**: `LOG_LEVEL` (DEBUG/INFO/WARNING/ERROR)
- **LangSmith**: `LANGSMITH_API_KEY`, `LANGSMITH_TRACING` (optional, for debugging)

## Project Structure

```
src/
  api/              # FastAPI application
  agents/           # LangGraph agent definitions
  core/             # Database, config, utilities
  models/           # SQLAlchemy ORM models
  schemas/          # Pydantic request/response schemas
tests/              # pytest test suite
evals/              # Evaluation suite with metrics
scripts/            # Utility scripts
```

## Development Workflow

1. Make changes to code
2. Run tests: `just test`
3. Format code: `just fmt`
4. Check linting: `just lint`
5. Test against live DB if needed: `just test-sql`
6. Commit and push

## Common Issues

See `CLAUDE.md` for known issues and patterns, including:
- SQLAlchemy `DetachedInstanceError` with LangGraph
- Session configuration for async contexts
