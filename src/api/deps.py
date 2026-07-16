"""FastAPI dependencies for dependency injection."""

from collections.abc import Generator

from sqlalchemy.orm import Session

from src.models.base import SessionLocal


def get_db() -> Generator[Session, None, None]:
    """Get database session for request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
