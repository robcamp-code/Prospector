# Prospector Development Recipes

# Default recipe - show available commands
default:
    @just --list

# Install dependencies
install:
    uv sync

# Run database migrations
migrate:
    alembic upgrade head

# Load ZIP code data from CSV
load-zips:
    python scripts/load_uszips.py

# Start development server
dev:
    uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Start development server with auto-reload on all files
dev-watch:
    uvicorn src.api.main:app --reload --reload-dir src --host 0.0.0.0 --port 8000

# Run all tests
test:
    pytest tests/ -v

# Run tests with coverage
test-cov:
    pytest tests/ -v --cov=src --cov-report=term-missing

# Create a new migration
migration name:
    alembic revision --autogenerate -m "{{name}}"

# Reset database (drop and recreate tables)
db-reset:
    alembic downgrade base
    alembic upgrade head

# Full setup: install, migrate, load data
setup: install migrate load-zips
    @echo "Setup complete! Run 'just dev' to start the server."

# Open API docs in browser
docs:
    open http://localhost:8000/docs

# Check code with ruff
lint:
    ruff check src/ tests/

# Format code with ruff
fmt:
    ruff format src/ tests/

# Run User Persona Agent on eval query
user-persona:
    python scripts/run_user_persona.py

# Run User Persona Agent with a custom query
user-persona-query query:
    echo "{{query}}" | python -c "import asyncio; from src.agents.user_persona import UserPersonaAgent; agent = UserPersonaAgent(); print(asyncio.run(agent.run(input().strip())))"

# Run Orchestrator Agent (fresh conversation)
orchestrator:
    python scripts/run_orchestrator.py

# Continue Orchestrator conversation with existing chat ID
orchestrator-continue chat_id:
    python scripts/run_orchestrator.py {{chat_id}}

# Run Orchestrator with a custom query
orchestrator-query query:
    python scripts/run_orchestrator.py -q "{{query}}"
