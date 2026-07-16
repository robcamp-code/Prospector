"""API route modules."""

from src.api.routes.profiles import router as profiles_router
from src.api.routes.reports import router as reports_router
from src.api.routes.zips import router as zips_router

__all__ = ["profiles_router", "reports_router", "zips_router"]
