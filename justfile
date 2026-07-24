# Prospector Development Recipes

# Load .env file
set dotenv-load

# Set PYTHONPATH for all recipes
export PYTHONPATH := "."

# Unbuffered stdout so print() output appears live during long runs
export PYTHONUNBUFFERED := "1"

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
# Testing
# ============================================================

# Run fast tests (no external APIs)
test:
    pytest tests/ -v -m "not live"

# Run live end-to-end tests (real LLM + DB via the API; slow, costs tokens)
test-live:
    pytest tests/ -v -m live

# Run tests with coverage
test-cov:
    pytest tests/ -v --cov=src --cov-report=term-missing -m "not live"

# ============================================================
# Evaluation
# ============================================================

# Run full evaluation suite (resumes: skips businesses with existing results)
eval:
    python evals/run_eval.py

# Evaluate a single business by id (always re-runs it)
# Example: just eval-one 01_cultura_connect
eval-one id:
    python evals/run_eval.py --only {{id}}

# Re-run the entire dataset, ignoring existing results
eval-force:
    python evals/run_eval.py --force

# ============================================================
# Code Quality
# ============================================================

# Check code with ruff
lint:
    ruff check src/ tests/

# Format code with ruff
fmt:
    ruff format src/ tests/
