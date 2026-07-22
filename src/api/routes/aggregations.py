"""Geographic and demographic aggregation endpoints."""

from typing import Literal

from fastapi import Depends, Query
from fastapi.routing import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db
from src.core.services.zips import get_aggregation
from src.schemas.aggregation import AggregationResponse, GeographyLevel

router = APIRouter(tags=["aggregations"])


@router.get("/get-aggregation", response_model=AggregationResponse)
async def aggregate_zip_data(
    group_by: GeographyLevel,
    metrics: list[str] = Query(
        ...,
        description="One or more 'category.metric' selectors, e.g., 'race.distribution', 'race.hispanic'. "
        "Repeated query param: ?metrics=race.distribution&metrics=income.median_household_income",
    ),
    region: str | None = Query(None, description="Optional region name (east_coast, west_coast, midwest, south, mountain_west)"),
    state: str | None = Query(None, description="Optional state name (exact match, e.g., 'Georgia')"),
    county: str | None = Query(None, description="Optional county name (exact match, e.g., 'Fulton County')"),
    cbsa: str | None = Query(None, description="Optional CBSA name (exact match)"),
    city: str | None = Query(None, description="Optional city name (exact match)"),
    sort_by: str | None = Query(None, description="Column to sort by (e.g., 'population', 'race.black', 'income.median_household_income')"),
    sort_dir: Literal["asc", "desc"] = Query("desc", description="Sort direction"),
    limit: int = Query(default=50, ge=1, le=1000, description="Number of rows to return"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    session: AsyncSession = Depends(get_db),
) -> AggregationResponse:
    """Aggregate ZIP code data by geography level with optional demographic metrics.

    This endpoint groups US ZIP codes by a chosen geographic level (zip, county, state, cbsa, region)
    and computes population-weighted aggregates of demographic metrics.

    Geographic filters (region, state, county, cbsa, city) are combined with AND logic and are optional —
    use any combination to narrow the result set.

    Metrics are specified as 'category.metric' strings (e.g., 'race.distribution', 'income.median_household_income').
    Use /get-demographic-categories and /get-demographic-metrics to discover available options.

    Example: ?group_by=county&state=Georgia&metrics=race.distribution&sort_by=race.black&sort_dir=desc&limit=10
    """
    return await get_aggregation(
        session,
        group_by=group_by,
        metric_selectors=metrics,
        region=region,
        state=state,
        county=county,
        cbsa=cbsa,
        city=city,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
    )
