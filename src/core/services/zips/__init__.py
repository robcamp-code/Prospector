"""ZIP code geography, demographics, and aggregation service.

Public API for ZIP code data queries.
"""

from src.core.services.zips.aggregation import AggregationQueryBuilder
from src.core.services.zips.demographics import (
    get_demographic_categories,
    get_demographic_metrics,
)
from src.core.services.zips.filters import GeographicFilters
from src.core.services.zips.geography import (
    get_region_list,
    list_cbsa_names,
    list_counties,
    list_zips,
)
from src.core.services.zips.metrics import MetricColumnBuilder

__all__ = [
    # Geography lookups
    "list_cbsa_names",
    "list_counties",
    "list_zips",
    "get_region_list",
    # Demographics discovery
    "get_demographic_categories",
    "get_demographic_metrics",
    # Aggregation builders (for direct use or extension)
    "AggregationQueryBuilder",
    "GeographicFilters",
    "MetricColumnBuilder",
]


# Convenience function for the API route
async def get_aggregation(
    session,
    group_by,
    metric_selectors,
    region=None,
    state=None,
    states=None,
    county=None,
    cbsa=None,
    city=None,
    min_density=None,
    max_density=None,
    sort_by=None,
    sort_dir="desc",
    limit=50,
    offset=0,
):
    """Aggregate ZIP code data by geography level with optional metrics.

    This endpoint groups US ZIP codes by a chosen geographic level (zip, county, state, cbsa, region)
    and computes population-weighted aggregates of demographic metrics.

    Args:
        session: AsyncSession for database access
        group_by: GeographyLevel to group by
        metric_selectors: List of 'category.metric' strings
        region: Optional region name
        state: Optional state name
        states: Optional list of state names (state_name IN (...))
        county: Optional county name
        cbsa: Optional CBSA name
        city: Optional city name
        min_density: Optional ZIP-row density floor (people/km², applied before grouping)
        max_density: Optional ZIP-row density ceiling (people/km², applied before grouping)
        sort_by: Optional column to sort by
        sort_dir: Sort direction ('asc' or 'desc')
        limit: Number of rows to return (1-1000)
        offset: Offset for pagination

    Returns:
        AggregationResponse with rows, limit, offset, total_count
    """
    builder = AggregationQueryBuilder(
        session,
        group_by,
        metric_selectors,
        sort_by=sort_by,
        sort_dir=sort_dir,
        limit=limit,
        offset=offset,
        region=region,
        state=state,
        states=states,
        county=county,
        cbsa=cbsa,
        city=city,
        min_density=min_density,
        max_density=max_density,
    )
    return await builder.execute()


__all__.append("get_aggregation")
