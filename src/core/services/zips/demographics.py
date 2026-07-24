"""Demographics lookup functions for ZIP codes."""

from fastapi import HTTPException

from src.core.demographics import DEMOGRAPHICS
from src.schemas.demographics import (
    CategoryInfo,
    DemographicCategoriesResponse,
    DemographicMetricsResponse,
    MetricInfo,
)


def get_demographic_categories() -> DemographicCategoriesResponse:
    """Get all demographic categories."""
    categories = [
        CategoryInfo(
            key=name,
            display_name=cat.display_name,
            metric_keys=list(cat.metrics.keys()),
        )
        for name, cat in DEMOGRAPHICS.categories.items()
    ]
    return DemographicCategoriesResponse(categories=categories)


def get_demographic_metrics(category: str) -> DemographicMetricsResponse:
    """Get all metrics for a specific category."""
    if category not in DEMOGRAPHICS.categories:
        raise HTTPException(status_code=400, detail=f"Unknown category: {category}")
    cat = DEMOGRAPHICS.get_category(category)
    metrics = [
        MetricInfo(
            key=k,
            type=m.type,
            column=m.column,
            columns=m.columns,
        )
        for k, m in cat.metrics.items()
    ]
    return DemographicMetricsResponse(
        category=category, display_name=cat.display_name, metrics=metrics
    )
