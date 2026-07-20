# Prospector - Development Notes

## Known Issues & Patterns

### SQLAlchemy DetachedInstanceError with LangGraph

When passing SQLAlchemy ORM objects through LangGraph state between nodes, you may encounter `DetachedInstanceError` when accessing model attributes after the session is closed.

**Root Cause**: By default, SQLAlchemy expires all attributes after `session.commit()`. When the session closes and later code tries to access those attributes, SQLAlchemy attempts to lazy-load them from the database, but the session is gone.

**Solution**: Use `expire_on_commit=False` in the session factory configuration:

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,  # Prevents DetachedInstanceError
)
```

This is configured in `src/core/database.py`. When wiring up API routes, ensure you use `AsyncSessionLocal` (or the `get_db` dependency) rather than creating raw `AsyncSession(engine)` instances.

**Affected Files**:
- `src/core/database.py` - Session factory configuration
- `src/agents/orchestrator/agent.py` - Uses sessions for persisting ClientProfile
