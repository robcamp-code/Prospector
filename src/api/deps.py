"""FastAPI dependencies."""

from fastapi import HTTPException

from src.core.database import get_db


def require_at_most_one(**filters: str | None) -> None:
    """Raise 400 if more than one of the given named filters is non-None.

    Used for endpoints where the caller must provide at most one of several
    mutually-exclusive geographic filters.

    Args:
        **filters: Named keyword arguments representing optional filters.

    Raises:
        HTTPException: 400 if more than one filter is provided.
    """
    provided = [name for name, value in filters.items() if value is not None]
    if len(provided) > 1:
        raise HTTPException(
            status_code=400,
            detail=f"Provide at most one of: {', '.join(filters.keys())}. Got: {', '.join(provided)}.",
        )


__all__ = ["get_db", "require_at_most_one"]
