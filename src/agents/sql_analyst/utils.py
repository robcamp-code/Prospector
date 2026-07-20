"""Query builders and utilities for SQL Analyst agent."""

from enum import StrEnum

from src.agents.orchestrator.demographics import DEMOGRAPHICS, Metric, MetricType
from src.agents.sql_analyst.templates import BASE_CTE_TEMPLATE
from src.core.logging import get_logger
from src.core.region import get_states_by_region
from src.core.state import DemographicTargetRef

logger = get_logger(__name__)


class GeographyLevel(StrEnum):
    """Geography aggregation levels for demographic queries."""

    COUNTY = "county"  # GROUP BY county_name, state_name
    STATE = "state"  # GROUP BY state_name
    CBSA = "cbsa"  # GROUP BY cbsa_name
    REGION = "region"  # GROUP BY region (with state IN clause)
    ZIP = "zip" # GROUP BY zip


def drill_down_level(
    state_names: list[str] | None = None,
    county_name: str | None = None,
    region_name: str | None = None,
    cbsa_names: list[str] | None = None,
) -> GeographyLevel:
    """Aggregation level for chartable queries: one level below the
    narrowest geography filter, so results always contain multiple
    comparable areas (counties within a metro/state, states within a
    region or the nation). Filtering AND grouping at the same level
    returns one row per filtered geography — a single-bar chart.
    """
    if county_name:
        return GeographyLevel.ZIP
    if cbsa_names:
        return GeographyLevel.COUNTY
    if state_names:
        return GeographyLevel.COUNTY
    return GeographyLevel.STATE  # region or nationwide


def get_group_by_cols(level: GeographyLevel) -> str:
    """Get GROUP BY columns for a geography level."""
    match level:
        case GeographyLevel.ZIP:
            return "zip, city, county_name, state_name"
        case GeographyLevel.COUNTY:
            return "county_name, state_name"
        case GeographyLevel.STATE:
            return "state_name"
        case GeographyLevel.CBSA:
            return "cbsa_name"
        case GeographyLevel.REGION:
            return "state_name"  # Group by state, filter by region


def get_select_cols(level: GeographyLevel) -> str:
    """Get SELECT columns for a geography level."""
    match level:
        case GeographyLevel.ZIP:
            return "zip, city, county_name, state_name"
        case GeographyLevel.COUNTY:
            return "county_name, state_name"
        case GeographyLevel.STATE:
            return "state_name"
        case GeographyLevel.CBSA:
            return "cbsa_name"
        case GeographyLevel.REGION:
            return "state_name"


# =============================================================================
# Geographic WHERE Clause Builders
# =============================================================================


def build_geography_filter(
    level: GeographyLevel,
    state_names: list[str] | None = None,
    county_name: str | None = None,
    region_name: str | None = None,
    cbsa_names: list[str] | None = None,
) -> str:
    """Build WHERE clause fragment for geography filtering.

    Returns SQL fragment with :param placeholders for parameterized values
    (single values) or literal IN clauses (for lists).

    Args:
        level: Geography aggregation level
        state_names: List of state names to filter by (uses IN clause)
        county_name: Single county name (uses parameterized query)
        region_name: Region name (expands to IN clause via get_states_by_region)
        cbsa_names: List of CBSA names to filter by (uses IN clause)

    Returns:
        SQL WHERE clause fragment
    """
    clauses = [
        "population IS NOT NULL",
        "population != 'NaN'::float8",
        "population > 0",
    ]

    if state_names:
        if len(state_names) == 1:
            clauses.append("state_name = :state_name")
        else:
            state_list = ", ".join(f"'{s}'" for s in state_names)
            clauses.append(f"state_name IN ({state_list})")

    if county_name:
        clauses.append("county_name = :county_name")

    if cbsa_names:
        if len(cbsa_names) == 1:
            clauses.append("cbsa_name = :cbsa_name")
        else:
            cbsa_list = ", ".join(f"'{c}'" for c in cbsa_names)
            clauses.append(f"cbsa_name IN ({cbsa_list})")

    if region_name:
        states = get_states_by_region(region_name)
        state_list = ", ".join(f"'{s}'" for s in states)
        clauses.append(f"state_name IN ({state_list})")

    return " AND ".join(clauses)


# =============================================================================
# Demographic WHERE Clause Builders (Hard Cutoff Filters)
# =============================================================================


def resolve_demographic_column(key: str) -> str | None:
    """Resolve a demographic_key to the actual uszips SQL column.

    Targets are stored with DEMOGRAPHICS metric names (e.g.
    'median_household_income'), but SQL needs the column name
    ('income_household_median'). Accepts either form; returns None if the
    key matches neither, so callers can skip it instead of emitting
    invalid SQL.
    """
    for category in DEMOGRAPHICS.categories.values():
        for metric_name, metric in category.metrics.items():
            if metric.type == MetricType.DISTRIBUTION:
                if metric.columns and key in metric.columns.values():
                    return key
            elif metric_name == key or metric.column == key:
                return metric.column
    return None


def build_demographic_filter(target: DemographicTargetRef) -> str:
    """Build WHERE clause fragment for a single DemographicTargetRef.

    This creates a hard cutoff filter - rows not meeting the criteria
    are excluded from results entirely. Targets whose key cannot be
    resolved to a real column are skipped (with a warning) rather than
    producing invalid SQL that would fail the whole query.
    """
    key = resolve_demographic_column(target.demographic_key)
    if key is None:
        logger.warning(
            f"build_demographic_filter: unresolvable demographic_key "
            f"'{target.demographic_key}', skipping filter"
        )
        return ""

    if target.constraint_type == "range":
        clauses = []
        if target.min_value is not None:
            clauses.append(f"{key} >= {target.min_value}")
        if target.max_value is not None:
            clauses.append(f"{key} <= {target.max_value}")
        return " AND ".join(clauses) if clauses else ""

    elif target.constraint_type == "threshold_min":
        if target.min_value is not None:
            return f"{key} >= {target.min_value}"

    elif target.constraint_type == "threshold_max":
        if target.max_value is not None:
            return f"{key} <= {target.max_value}"

    elif target.constraint_type == "percentage":
        if target.target_percentage is not None:
            op_map = {"gt": ">", "lt": "<", "gte": ">=", "lte": "<=", "eq": "="}
            op = op_map.get(target.percentage_operator or "gte", ">=")
            return f"{key} {op} {target.target_percentage}"

    return ""


def build_demographic_where(targets: list[DemographicTargetRef] | None) -> str:
    """Build combined WHERE clause from multiple demographic targets.

    Returns "TRUE" if no targets, so it can be safely ANDed with other clauses.
    """
    if not targets:
        return "TRUE"

    filters = [build_demographic_filter(t) for t in targets]
    filters = [f for f in filters if f]  # Remove empty strings

    return " AND ".join(filters) if filters else "TRUE"


# =============================================================================
# Query Builders
# =============================================================================


def build_order_clause(order_by: str | None, order_desc: bool) -> str:
    """Build ORDER BY clause."""
    if not order_by:
        return ""
    direction = "DESC" if order_desc else "ASC"
    return f"ORDER BY {order_by} {direction}"


def build_distribution_query(
    metric: Metric,
    geography_level: GeographyLevel,
    state_names: list[str] | None,
    county_name: str | None,
    region_name: str | None,
    cbsa_names: list[str] | None,
    demographic_targets: list[DemographicTargetRef] | None,
    order_by: str | None,
    order_desc: bool,
) -> str:
    """Build SQL query for DISTRIBUTION metric type.

    Distribution metrics aggregate multiple columns (e.g., race_white, race_black)
    and calculate population-weighted percentages for each.
    """
    if not metric.columns:
        raise ValueError("DISTRIBUTION metric requires 'columns' to be defined")

    group_by_cols = get_group_by_cols(geography_level)
    select_cols = get_select_cols(geography_level)

    # Build WHERE clause combining geography and demographic filters
    geo_where = build_geography_filter(
        geography_level, state_names, county_name, region_name, cbsa_names
    )
    demo_where = build_demographic_where(demographic_targets)
    where_clause = f"{geo_where} AND {demo_where}"

    # Build CTE aggregations for each column
    agg_parts = []
    for col_name in metric.columns.values():
        agg_parts.append(
            f"SUM(population * COALESCE(NULLIF({col_name}, 'NaN'::float8), 0) / 100.0) AS {col_name}_pop"
        )
    aggregation_expressions = ", ".join(agg_parts)

    # Build percentage calculations in the outer SELECT
    final_parts = []
    for col_name in metric.columns.values():
        final_parts.append(f"{col_name}_pop * 100.0 / population AS {col_name}")
    final_expressions = ", ".join(final_parts)

    order_clause = build_order_clause(order_by, order_desc)

    return BASE_CTE_TEMPLATE.format(
        group_by_cols=group_by_cols,
        select_cols=select_cols,
        where_clause=where_clause,
        aggregation_expressions=aggregation_expressions,
        final_expressions=final_expressions,
        order_clause=order_clause,
    ).strip()


def build_percentage_query(
    metric: Metric,
    geography_level: GeographyLevel,
    state_names: list[str] | None,
    county_name: str | None,
    region_name: str | None,
    cbsa_names: list[str] | None,
    demographic_targets: list[DemographicTargetRef] | None,
    order_by: str | None,
    order_desc: bool,
) -> str:
    """Build SQL query for PERCENTAGE metric type.

    Percentage metrics aggregate a single column representing a percentage
    using population weighting.
    """
    if not metric.column:
        raise ValueError("PERCENTAGE metric requires 'column' to be defined")

    group_by_cols = get_group_by_cols(geography_level)
    select_cols = get_select_cols(geography_level)
    col_name = metric.column

    # Build WHERE clause
    geo_where = build_geography_filter(
        geography_level, state_names, county_name, region_name, cbsa_names
    )
    demo_where = build_demographic_where(demographic_targets)
    where_clause = f"{geo_where} AND {demo_where}"

    # CTE aggregation for percentage column
    aggregation_expressions = (
        f"SUM(population * COALESCE(NULLIF({col_name}, 'NaN'::float8), 0) / 100.0) AS {col_name}_pop"
    )

    # Final calculation: weighted percentage
    final_expressions = f"{col_name}_pop * 100.0 / population AS {col_name}"

    order_clause = build_order_clause(order_by, order_desc)

    return BASE_CTE_TEMPLATE.format(
        group_by_cols=group_by_cols,
        select_cols=select_cols,
        where_clause=where_clause,
        aggregation_expressions=aggregation_expressions,
        final_expressions=final_expressions,
        order_clause=order_clause,
    ).strip()


def build_numeric_query(
    metric: Metric,
    geography_level: GeographyLevel,
    state_names: list[str] | None,
    county_name: str | None,
    region_name: str | None,
    cbsa_names: list[str] | None,
    demographic_targets: list[DemographicTargetRef] | None,
    order_by: str | None,
    order_desc: bool,
) -> str:
    """Build SQL query for NUMERIC metric type.

    Numeric metrics (e.g., median_age, median_income) are aggregated using
    population-weighted averages: SUM(population * col) / SUM(population)
    """
    if not metric.column:
        raise ValueError("NUMERIC metric requires 'column' to be defined")

    group_by_cols = get_group_by_cols(geography_level)
    select_cols = get_select_cols(geography_level)
    col_name = metric.column

    # Build WHERE clause
    geo_where = build_geography_filter(
        geography_level, state_names, county_name, region_name, cbsa_names
    )
    demo_where = build_demographic_where(demographic_targets)
    where_clause = f"{geo_where} AND {demo_where}"

    # CTE aggregation: population-weighted sum
    aggregation_expressions = (
        f"SUM(population * COALESCE(NULLIF({col_name}, 'NaN'::float8), 0)) AS {col_name}_weighted"
    )

    # Final calculation: weighted average
    final_expressions = f"{col_name}_weighted / NULLIF(population, 0) AS {col_name}"

    order_clause = build_order_clause(order_by, order_desc)

    return BASE_CTE_TEMPLATE.format(
        group_by_cols=group_by_cols,
        select_cols=select_cols,
        where_clause=where_clause,
        aggregation_expressions=aggregation_expressions,
        final_expressions=final_expressions,
        order_clause=order_clause,
    ).strip()
