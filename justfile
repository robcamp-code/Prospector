# Prospector Development Recipes

# Load .env file
set dotenv-load

# Set PYTHONPATH for all recipes
export PYTHONPATH := "."

# Default recipe - show available commands
default:
    @just --list

# ============================================================
# Setup & Dependencies
# ============================================================

# Install dependencies
install:
    uv sync

# Full setup: install, migrate, load data
setup: install migrate load-zips
    @echo "Setup complete! Run 'just dev' to start the server."

# ============================================================
# Development Server
# ============================================================

# Start development server
dev:
    uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Open API docs in browser
docs:
    open http://localhost:8000/docs

# ============================================================
# Database
# ============================================================

# Run database migrations
migrate:
    alembic upgrade head

# Create a new migration
migration name:
    alembic revision --autogenerate -m "{{name}}"

# Reset database (drop and recreate tables)
db-reset:
    alembic downgrade base
    alembic upgrade head

# Load ZIP code data from CSV
load-zips:
    python scripts/load_uszips.py

# ============================================================
# Chat Agent
# ============================================================

# Run interactive chat agent
chat:
    python scripts/run_chat.py

# Continue existing chat conversation
chat-continue id:
    python scripts/run_chat.py {{id}}

# Send a single message to chat agent
chat-message msg:
    python scripts/run_chat.py -m "{{msg}}"

# Run the orchestrator agent
orchestrator:
    uv run python src/agents/orchestrator/agent.py

# ============================================================
# Testing
# ============================================================

# Run all tests
test:
    pytest tests/ -v

# Run tests with coverage
test-cov:
    pytest tests/ -v --cov=src --cov-report=term-missing

# Run SQL analyst integration tests (live database)
test-sql:
    pytest tests/integration/test_sql_analyst_queries.py -v -s

# Run a specific SQL analyst test by name pattern
# Example: just test-sql-query hispanic
# Example: just test-sql-query "limited_english"
# Example: just test-sql-query "education_with_income"
test-sql-query pattern:
    pytest tests/integration/test_sql_analyst_queries.py -v -s -k "{{pattern}}"

# List available SQL analyst test names
test-sql-list:
    @pytest tests/integration/test_sql_analyst_queries.py --collect-only -q

# ============================================================
# Code Quality
# ============================================================

# Check code with ruff
lint:
    ruff check src/ tests/

# Format code with ruff
fmt:
    ruff format src/ tests/
