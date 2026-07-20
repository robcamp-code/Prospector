"""SQLModel database models.

Backwards compatibility shim - imports from new location at src.core.database.
"""

from src.core.database import (
    ClientProfile,
    DemographicTarget,
    DEMOGRAPHIC_KEY_MAPPING,
    USZip,
    async_engine,
    create_db_and_tables,
    get_db,
)

__all__ = [
    "ClientProfile",
    "DemographicTarget",
    "DEMOGRAPHIC_KEY_MAPPING",
    "USZip",
    "async_engine",
    "get_db",
    "create_db_and_tables",
]
