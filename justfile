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

# Run all tests
test:
    pytest tests/ -v

# Run tests with coverage
test-cov:
    pytest tests/ -v --cov=src --cov-report=term-missing

# ============================================================
# Code Quality
# ============================================================

# Check code with ruff
lint:
    ruff check src/ tests/

# Format code with ruff
fmt:
    ruff format src/ tests/
