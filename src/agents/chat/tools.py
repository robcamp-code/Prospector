"""Tool wrapper for get_aggregation service."""

import json
from langchain_core.tools import tool

from src.core.database import AsyncSessionLocal
from src.core.services.zips import get_aggregation
from src.schemas.aggregation import GeographyLevel


@tool
async def get_aggregation_tool(
    group_by: str,
    metrics: list[str],
    region: str | None = None,
    state: str | None = None,
    county: str | None = None,
    cbsa: str | None = None,
    city: str | None = None,
    sort_by: str | None = None,
    sort_dir: str = "desc",
    limit: int = 50,
) -> str:
    """Fetch aggregated demographic data for geographic regions.

    Args:
        group_by: Geography level to group results by (state, county, zip, city, cbsa, region)
        metrics: List of 'category.metric' strings (e.g., 'income.median_household_income')
        region: Optional region filter (e.g., "South", "Midwest")
        state: Optional state filter
        county: Optional county filter
        cbsa: Optional CBSA (metro area) filter
        city: Optional city filter
        sort_by: Metric to sort by (e.g., 'population' or 'income.median_household_income')
        sort_dir: 'asc' or 'desc'
        limit: Max rows to return (1-1000)

    Returns:
        JSON string of AggregationResponse with rows, limit, offset, total_count
    """
    async with AsyncSessionLocal() as session:
        try:
            response = await get_aggregation(
                session=session,
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
                offset=0,
            )
            return response.model_dump_json()
        except Exception as exc:
            return f"Error: {str(exc)}"
