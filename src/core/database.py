"""Centralized async database and checkpointer setup."""

from collections.abc import AsyncGenerator

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlmodel import SQLModel

from src.core.config import get_settings

settings = get_settings()
async_engine = create_async_engine(settings.async_database_url, echo=settings.debug)

# expire_on_commit=False prevents DetachedInstanceError when accessing
# model attributes after the session is closed. This is needed when passing
# ORM objects through LangGraph state between nodes.
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

_checkpointer: AsyncPostgresSaver | None = None
_checkpointer_cm = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Async database session dependency."""
    async with AsyncSessionLocal() as session:
        yield session


async def create_db_and_tables():
    """Create all database tables."""
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def init_checkpointer() -> None:
    """Initialize singleton checkpointer at startup."""
    global _checkpointer, _checkpointer_cm
    _checkpointer_cm = AsyncPostgresSaver.from_conn_string(settings.database_url)
    _checkpointer = await _checkpointer_cm.__aenter__()
    await _checkpointer.setup()


async def close_checkpointer() -> None:
    """Close checkpointer at shutdown."""
    global _checkpointer, _checkpointer_cm
    if _checkpointer_cm:
        await _checkpointer_cm.__aexit__(None, None, None)
        _checkpointer = None
        _checkpointer_cm = None


def get_checkpointer() -> AsyncPostgresSaver:
    """Get singleton checkpointer instance."""
    if _checkpointer is None:
        raise RuntimeError("Checkpointer not initialized. Call init_checkpointer() first.")
    return _checkpointer
