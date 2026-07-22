"""Parameterized demographic query functions for SQL Analyst agent."""

from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.orchestrator.demographics import (
    DEMOGRAPHICS,
    CategoryName,
    MetricType,
)
from src.agents.sql_analyst.utils import (
    GeographyLevel,
    build_distribution_query,
    build_numeric_query,
    build_percentage_query,
)
from src.core.logging import get_logger
from src.core.state import DemographicTargetRef

logger = get_logger(__name__)


class AggregatedDemographics(BaseModel):
    """Aggregated demographic data at geography level (reuses USZip field names)."""

    zip: str | None = None
    city: str | None = None
    county_name: str | None = None
    state_name: str | None = None
    cbsa_name: str | None = None
    population: float
    density: float | None = None

    # Dynamic demographic fields populated based on query
    model_config = ConfigDict(extra="allow")


async def query_aggregated_demographics(
    session: AsyncSession,
    category: CategoryName,
    metric_name: str = "distribution",
    # Geography filtering
    geography_level: GeographyLevel = GeographyLevel.COUNTY,
    state_names: list[str] | None = None,
    county_name: str | None = None,
    region_name: str | None = None,
    cbsa_names: list[str] | None = None,
    # Demographic filtering (hard cutoff)
    demographic_targets: list[DemographicTargetRef] | None = None,
    # Ordering
    order_by: str | None = None,
    order_desc: bool = True,
) -> list[AggregatedDemographics]:
    """Query aggregated demographic data at configurable geography level.

    Dynamically builds SQL queries based on the demographic categories defined
    in demographics.py. Returns population-weighted aggregated results.

    Args:
        session: AsyncSession for database access
        category: Demographic category name (e.g., "race", "age", "income")
        metric_name: Metric within the category (e.g., "distribution", "median_age")
        geography_level: Aggregation level (county, state, cbsa, region)
        state_names: List of state names to filter by (optional)
        county_name: Filter by county (optional)
        region_name: Filter by region name (e.g., "south", "midwest")
        cbsa_names: List of CBSA/metro area names to filter by (optional)
        demographic_targets: List of DemographicTargetRef for hard cutoff filtering
        order_by: Column to order results by (optional)
        order_desc: Order descending if True (default), ascending if False

    Returns:
        List of AggregatedDemographics with aggregated values at the specified level

    Example:
        # Get race distribution for Georgia counties, ordered by % Black
        results = await query_aggregated_demographics(
            session=session,
            category="race",
            metric_name="distribution",
            state_names=["Georgia"],
            order_by="race_black",
            order_desc=True,
        )

        # Get income data for South region with high-income filter
        results = await query_aggregated_demographics(
            session=session,
            category="income",
            metric_name="median_household_income",
            geography_level=GeographyLevel.STATE,
            region_name="south",
            demographic_targets=[
                DemographicTargetRef(
                    demographic_key="income_household_median",
                    constraint_type="threshold_min",
                    min_value=75000,
                )
            ],
            order_by="income_household_median",
            order_desc=True,
        )
    """
    # Get metric configuration from DEMOGRAPHICS mapping
    metric = DEMOGRAPHICS.get_metric(category, metric_name)

    # Build query based on metric type
    query_args = (
        metric,
        geography_level,
        state_names,
        county_name,
        region_name,
        cbsa_names,
        demographic_targets,
        order_by,
        order_desc,
    )

    if metric.type == MetricType.DISTRIBUTION:
        query = build_distribution_query(*query_args)
    elif metric.type == MetricType.PERCENTAGE:
        query = build_percentage_query(*query_args)
    elif metric.type == MetricType.NUMERIC:
        query = build_numeric_query(*query_args)
    else:
        raise ValueError(f"Unsupported metric type: {metric.type}")

    # Build parameters dict for parameterized values (single-value params only)
    params: dict[str, str] = {}
    if state_names and len(state_names) == 1:
        params["state_name"] = state_names[0]
    if county_name:
        params["county_name"] = county_name
    if cbsa_names and len(cbsa_names) == 1:
        params["cbsa_name"] = cbsa_names[0]

    logger.debug(
        f"query_aggregated_demographics: category={category}, metric={metric_name}, "
        f"level={geography_level.value}, params={params}"
    )

    # Execute query
    result = await session.execute(text(query), params)
    rows = result.mappings().all()

    logger.info(f"query_aggregated_demographics: returned {len(rows)} rows")
    if len(rows) == 0:
        logger.warning(
            f"ZERO ROWS! state_names={state_names}, cbsa_names={cbsa_names} may not exist in database"
        )

    # Convert to AggregatedDemographics models
    return [AggregatedDemographics(**dict(row)) for row in rows]
