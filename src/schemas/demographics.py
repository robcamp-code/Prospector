"""Demographics discovery endpoint request and response schemas."""

from pydantic import BaseModel

from src.core.demographics import CategoryName, MetricType


class MetricInfo(BaseModel):
    """Information about a single demographic metric."""

    key: str
    type: MetricType
    column: str | None = None
    columns: dict[str, str] | None = None


class CategoryInfo(BaseModel):
    """Information about a demographic category and its metrics."""

    key: CategoryName
    display_name: str
    metric_keys: list[str]


class DemographicCategoriesResponse(BaseModel):
    """Response for /get-demographic-categories endpoint."""

    categories: list[CategoryInfo]


class DemographicMetricsResponse(BaseModel):
    """Response for /get-demographic-metrics endpoint."""

    category: CategoryName
    display_name: str
    metrics: list[MetricInfo]
