"""Demographic discovery endpoints."""

from fastapi.routing import APIRouter

from src.agents.orchestrator.demographics import CategoryName
from src.core.services.zips import (
    get_demographic_categories,
    get_demographic_metrics,
)
from src.schemas.demographics import (
    DemographicCategoriesResponse,
    DemographicMetricsResponse,
)

router = APIRouter(tags=["demographics"])


@router.get("/get-demographic-categories", response_model=DemographicCategoriesResponse)
async def list_demographic_categories() -> DemographicCategoriesResponse:
    """Get all available demographic categories."""
    return get_demographic_categories()


@router.get("/get-demographic-metrics", response_model=DemographicMetricsResponse)
async def list_demographic_metrics(category: str) -> DemographicMetricsResponse:
    """Get all metrics available for a specific demographic category.

    Args:
        category: One of: race, age, employment, marital_status, income,
                  education, housing, health, community, language, transportation.

    Returns 400 if the category is unknown.
    """
    # CategoryName is a Literal, so validate against DEMOGRAPHICS directly
    from src.agents.orchestrator.demographics import DEMOGRAPHICS
    from fastapi import HTTPException

    if category not in DEMOGRAPHICS.categories:
        valid = ", ".join(DEMOGRAPHICS.categories.keys())
        raise HTTPException(
            status_code=400,
            detail=f"Unknown category '{category}'. Must be one of: {valid}",
        )
    return get_demographic_metrics(category)
