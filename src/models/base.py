"""Database configuration and session management using SQLModel.

Re-exports from core/database for backwards compatibility.
"""

from src.core.database import async_engine, create_db_and_tables, get_db

__all__ = [
    "async_engine",
    "create_db_and_tables",
    "get_db",
]
