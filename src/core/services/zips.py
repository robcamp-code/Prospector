"""ZIP code geography and demographic aggregation service."""

from enum import StrEnum
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql import ColumnElement

from src.core.demographics import DEMOGRAPHICS, CategoryName, MetricType
from src.core.database import USZip
from src.core.region.constants import REGIONS
from src.core.region.tools import get_states_by_region
from src.schemas.aggregation import AggregationResponse, AggregationRow, GeographyLevel
from src.schemas.demographics import (
    CategoryInfo,
    DemographicCategoriesResponse,
    DemographicMetricsResponse,
    MetricInfo,
)
from src.schemas.geography import RegionInfo


# Column mapping for each geography level
_GROUP_BY_COLUMNS: dict[GeographyLevel, list[InstrumentedAttribute]] = {
    GeographyLevel.ZIP: [USZip.zip, USZip.city, USZip.county_name, USZip.state_name],
    GeographyLevel.COUNTY: [USZip.county_name, USZip.state_name],
    GeographyLevel.STATE: [USZip.state_name],
    GeographyLevel.CITY: [USZip.city, USZip.state_name],
    GeographyLevel.CBSA: [USZip.cbsa_name],
    GeographyLevel.REGION: [USZip.state_name],
}


def _group_field_name(col: InstrumentedAttribute) -> str:
    """Get the key name for a column attribute."""
    return col.key


def _nan_safe(col: InstrumentedAttribute) -> ColumnElement:
    """Guard against NaN sentinels: COALESCE(NULLIF(col, NaN), 0).

    Relies on asyncpg parameter binding preserving NaN as Postgres NaN,
    and Postgres's non-IEEE754 equality check (NaN = NaN -> TRUE).
    Verified empirically in dev against known-NaN rows in race_white, etc.
    """
    return func.coalesce(func.nullif(col, float("nan")), 0)


def _apply_state_or_region(
    stmt,
    state: str | None,
    region: str | None,
) -> object:
    """Apply state or region filter to a select statement."""
    if state:
        return stmt.where(USZip.state_name == state)
    if region:
        try:
            states = get_states_by_region(region)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return stmt.where(USZip.state_name.in_(states))
    return stmt


# =============================================================================
# Geography lookups (distinct values)
# =============================================================================


async def list_cbsa_names(
    session: AsyncSession, state: str | None = None, region: str | None = None
) -> list[str]:
    """Get distinct CBSA (metro area) names."""
    stmt = (
        select(USZip.cbsa_name)
        .where(USZip.cbsa_name.is_not(None), USZip.cbsa_name != "")
        .distinct()
        .order_by(USZip.cbsa_name)
    )
    stmt = _apply_state_or_region(stmt, state, region)
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]


async def list_counties(
    session: AsyncSession,
    region: str | None = None,
    state: str | None = None,
    city: str | None = None,
) -> list[str]:
    """Get distinct county names."""
    stmt = (
        select(USZip.county_name)
        .where(USZip.county_name.is_not(None), USZip.county_name != "")
        .distinct()
        .order_by(USZip.county_name)
    )
    stmt = _apply_state_or_region(stmt, state, region)
    if city:
        stmt = stmt.where(USZip.city == city)
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]


async def list_zips(
    session: AsyncSession,
    county: str | None = None,
    state: str | None = None,
    city: str | None = None,
) -> list[str]:
    """Get distinct zip codes."""
    stmt = select(USZip.zip).where(USZip.zip.is_not(None)).distinct().order_by(USZip.zip)
    stmt = _apply_state_or_region(stmt, state, None)
    if county:
        stmt = stmt.where(USZip.county_name == county)
    if city:
        stmt = stmt.where(USZip.city == city)
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]


def get_region_list() -> list[RegionInfo]:
    """Get all regions with their member states."""
    return [
        RegionInfo(
            key=key,
            display_name=key.replace("_", " ").title(),
            states=[state.value for state in enum_cls],
        )
        for key, enum_cls in REGIONS.items()
    ]


# =============================================================================
# Demographics discovery (pure lookups over DEMOGRAPHICS)
# =============================================================================


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


# =============================================================================
# Aggregation query builder
# =============================================================================


def _parse_metric_selector(raw: str) -> tuple[str, str]:
    """Parse 'category.metric' string and validate against DEMOGRAPHICS."""
    parts = raw.split(".", 1)
    if len(parts) != 2:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric selector '{raw}', expected 'category.metric'",
        )
    category_str, metric_key = parts
    if category_str not in DEMOGRAPHICS.categories:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown category '{category_str}' in '{raw}'",
        )
    if metric_key not in DEMOGRAPHICS.get_category(category_str).metrics:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown metric '{metric_key}' in category '{category_str}'",
        )
    return category_str, metric_key


def _resolve_sort_label(sort_by: str, valid_labels: dict[str, ColumnElement]) -> str:
    """Resolve user-facing sort_by to actual internal SQL label.

    Ensures sort_by only references columns actually in this query's SELECT,
    preventing SQL injection by restricting to user-requested metrics only.
    """
    if sort_by in ("population", "density"):
        if sort_by in valid_labels:
            return sort_by
        raise HTTPException(status_code=400, detail=f"sort_by '{sort_by}' not available")

    # Try direct __ replacement: "race.black" -> "race__black"
    candidate_flat = sort_by.replace(".", "__")
    if candidate_flat in valid_labels:
        return candidate_flat

    # Try distribution form: "race.black" might be "race__distribution__black"
    if "." in sort_by:
        category_str, subkey = sort_by.split(".", 1)
        matches = [
            l
            for l in valid_labels.keys()
            if l.startswith(f"{category_str}__") and l.endswith(f"__{subkey}")
        ]
        if len(matches) == 1:
            return matches[0]

    raise HTTPException(
        status_code=400,
        detail=f"sort_by '{sort_by}' does not match any requested metric",
    )


def _build_metric_columns(category: str, metric_key: str) -> dict[str, ColumnElement]:
    """Build labeled column expressions for one requested metric.

    Returns {label: ColumnElement} for a DISTRIBUTION metric (one per sub-key)
    or a single entry for PERCENTAGE/NUMERIC.
    """
    metric = DEMOGRAPHICS.get_metric(category, metric_key)
    pop = USZip.population
    out = {}

    if metric.type == MetricType.DISTRIBUTION:
        for subkey, col_name in metric.columns.items():
            col = getattr(USZip, col_name)
            label = f"{category}__{metric_key}__{subkey}"
            # Weighted population percentage: SUM(population * pct/100) * 100 / SUM(population)
            # Guard the population value itself against NaN
            out[label] = (
                func.sum(_nan_safe(pop) * _nan_safe(col) / 100.0) * 100.0
                / func.sum(_nan_safe(pop))
            ).label(label)
    elif metric.type == MetricType.PERCENTAGE:
        col = getattr(USZip, metric.column)
        label = f"{category}__{metric_key}"
        out[label] = (
            func.sum(_nan_safe(pop) * _nan_safe(col) / 100.0) * 100.0
            / func.sum(_nan_safe(pop))
        ).label(label)
    elif metric.type == MetricType.NUMERIC:
        col = getattr(USZip, metric.column)
        label = f"{category}__{metric_key}"
        out[label] = (
            func.sum(_nan_safe(pop) * _nan_safe(col))
            / func.nullif(func.sum(_nan_safe(pop)), 0)
        ).label(label)

    return out


async def get_aggregation(
    session: AsyncSession,
    group_by: GeographyLevel,
    metric_selectors: list[str],
    region: str | None = None,
    state: str | None = None,
    county: str | None = None,
    cbsa: str | None = None,
    city: str | None = None,
    sort_by: str | None = None,
    sort_dir: Literal["asc", "desc"] = "desc",
    limit: int = 50,
    offset: int = 0,
) -> AggregationResponse:
    """Build and execute the dynamic aggregation query."""
    # Parse and deduplicate metric selectors
    parsed_metrics = [_parse_metric_selector(s) for s in metric_selectors]
    parsed_metrics = list(dict.fromkeys(parsed_metrics))  # Deduplicate

    # Get group-by columns
    group_cols = _GROUP_BY_COLUMNS[group_by]

    # Build metric columns
    metric_columns: dict[str, ColumnElement] = {}
    metric_to_labels: dict[tuple[str, str], list[str]] = {}
    for category, metric_key in parsed_metrics:
        cols = _build_metric_columns(category, metric_key)
        metric_columns.update(cols)
        metric_to_labels[(category, metric_key)] = list(cols.keys())

    # Build population and density columns (with NaN safety)
    population_col = func.sum(_nan_safe(USZip.population)).label("population")
    area_col = func.sum(
        case(
            (
                and_(USZip.density.is_not(None), USZip.density > 0),
                _nan_safe(USZip.population) / USZip.density,
            ),
            else_=0.0,
        )
    ).label("estimated_area_km2")
    density_col = (population_col / func.nullif(area_col, 0)).label("density")

    # Build the SELECT statement
    stmt = select(*group_cols, population_col, density_col, *metric_columns.values())

    # Apply WHERE clauses
    stmt = stmt.where(
        USZip.population.is_not(None),
        USZip.population > 0,
    )

    # Apply geographic filters (AND-combinable)
    if state:
        stmt = stmt.where(USZip.state_name == state)
    if region:
        try:
            states = get_states_by_region(region)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        stmt = stmt.where(USZip.state_name.in_(states))
    if county:
        stmt = stmt.where(USZip.county_name == county)
    if cbsa:
        stmt = stmt.where(USZip.cbsa_name == cbsa)
    if city:
        stmt = stmt.where(USZip.city == city)

    # GROUP BY and post-aggregation filter
    stmt = stmt.group_by(*group_cols)
    stmt = stmt.having(func.sum(_nan_safe(USZip.population)) > 0)

    # ORDER BY (resolve sort_by to an actual label first)
    all_labels = {"population": population_col, "density": density_col, **metric_columns}
    if sort_by:
        resolved_sort_label = _resolve_sort_label(sort_by, all_labels)
        sort_col = all_labels[resolved_sort_label]
    else:
        sort_col = population_col
        resolved_sort_label = "population"

    if sort_dir == "desc":
        stmt = stmt.order_by(sort_col.desc())
    else:
        stmt = stmt.order_by(sort_col.asc())

    # LIMIT and OFFSET
    stmt = stmt.limit(limit).offset(offset)

    # Execute and shape results
    result = await session.execute(stmt)
    rows = []
    for row_mapping in result.mappings():
        group_dict = {_group_field_name(col): row_mapping[_group_field_name(col)] for col in group_cols}
        population = row_mapping["population"]
        density = row_mapping["density"]

        # Build metrics dict, converting internal labels back to user-facing dotted form
        metrics_dict: dict[str, float | dict[str, float]] = {}
        for (category, metric_key), labels in metric_to_labels.items():
            metric = DEMOGRAPHICS.get_metric(category, metric_key)
            user_key = f"{category}.{metric_key}"

            if metric.type == MetricType.DISTRIBUTION:
                # Sub-keys go into a nested dict
                sub_dict = {}
                for label in labels:
                    # Extract subkey from label: "category__metric__subkey" -> "subkey"
                    subkey = label.rsplit("__", 1)[-1]
                    sub_dict[subkey] = float(row_mapping[label]) if row_mapping[label] is not None else 0.0
                metrics_dict[user_key] = sub_dict
            else:
                # PERCENTAGE/NUMERIC: flat float
                label = labels[0]
                metrics_dict[user_key] = float(row_mapping[label]) if row_mapping[label] is not None else 0.0

        rows.append(
            AggregationRow(
                group=group_dict,
                population=float(population) if population is not None else 0.0,
                density=float(density) if density is not None else None,
                metrics=metrics_dict,
            )
        )

    return AggregationResponse(rows=rows, limit=limit, offset=offset, total_count=None)
