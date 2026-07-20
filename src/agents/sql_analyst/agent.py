"""SQL Agent for generating demographic reports with visualizations."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.orchestrator.demographics import DEMOGRAPHICS, MetricType
from src.agents.sql_analyst.tools import (
    AggregatedDemographics,
    query_aggregated_demographics,
)
from src.agents.sql_analyst.transformers import (
    to_bubble_data,
    to_categorical_data,
    to_distribution_data,
)
from src.agents.sql_analyst.utils import GeographyLevel
from src.core.logging import get_logger
from src.core.state import ClientProfileRef, DemographicTargetRef
from src.schemas.report import (
    Report,
    ReportSection,
    ReportSummary,
    Visualization,
    VisualizationConfig,
)

logger = get_logger(__name__)


async def generate_report(
    session: AsyncSession,
    client_profile: ClientProfileRef,
    geography_level: GeographyLevel = GeographyLevel.STATE,
    state_names: list[str] | None = None,
    county_name: str | None = None,
    region_name: str | None = None,
    cbsa_names: list[str] | None = None,
) -> Report:
    """Generate a demographic report for the specified geography.

    Main entry point for the SQL agent. Builds a complete Report
    with summary statistics, bubble chart, and sections for each
    target demographic.

    Args:
        session: AsyncSession for database access
        client_profile: Client profile with target demographics
        geography_level: Aggregation level for queries
        state_names: List of state names to filter by
        county_name: Filter by county
        region_name: Filter by region
        cbsa_names: List of CBSA names to filter by

    Returns:
        Complete Report with summary and sections
    """
    logger.info(
        f"generate_report: state_names={state_names}, cbsa_names={cbsa_names}, "
        f"region_name={region_name}, level={geography_level.value}"
    )
    # Build geography value string for report title
    geography_value = _build_geography_value(
        state_names, county_name, region_name, cbsa_names
    )

    # Build summary with bubble chart
    summary = await _build_summary(
        session=session,
        geography_level=geography_level,
        state_names=state_names,
        county_name=county_name,
        region_name=region_name,
        cbsa_names=cbsa_names,
    )

    # Build sections from target_demographics
    sections = await _build_sections(
        session=session,
        target_demographics=client_profile.target_demographics,
        geography_level=geography_level,
        state_names=state_names,
        county_name=county_name,
        region_name=region_name,
        cbsa_names=cbsa_names,
    )

    return Report(
        report_id=str(uuid4()),
        title=f"Demographic Report: {geography_value}",
        subtitle=f"Analysis for {client_profile.name or 'Your Business'}",
        geography_type=geography_level.value,
        geography_value=geography_value,
        client_profile_id=client_profile.profile_id,
        summary=summary,
        sections=sections,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def _build_geography_value(
    state_names: list[str] | None,
    county_name: str | None,
    region_name: str | None,
    cbsa_names: list[str] | None,
) -> str:
    """Build a human-readable geography description."""
    if county_name and state_names and len(state_names) == 1:
        return f"{county_name}, {state_names[0]}"
    if state_names:
        if len(state_names) == 1:
            return state_names[0]
        if len(state_names) <= 3:
            return ", ".join(state_names)
        return f"{len(state_names)} States"
    if cbsa_names:
        if len(cbsa_names) == 1:
            return cbsa_names[0]
        if len(cbsa_names) <= 3:
            # Extract just the city name from full CBSA for readability
            short_names = [c.split("-")[0] for c in cbsa_names]
            return ", ".join(short_names)
        return f"{len(cbsa_names)} Metro Areas"
    if region_name:
        return f"{region_name.replace('_', ' ').title()} Region"
    return "United States"


async def _build_summary(
    session: AsyncSession,
    geography_level: GeographyLevel,
    state_names: list[str] | None,
    county_name: str | None,
    region_name: str | None,
    cbsa_names: list[str] | None,
) -> ReportSummary:
    """Build report summary with aggregate statistics and bubble chart."""
    # Query summary statistics at ZIP level for granularity
    zip_results = await query_aggregated_demographics(
        session=session,
        category="income",
        metric_name="median_household_income",
        geography_level=GeographyLevel.ZIP,
        state_names=state_names,
        county_name=county_name,
        region_name=region_name,
        cbsa_names=cbsa_names,
    )

    # Calculate summary statistics
    total_population = sum(int(r.population) for r in zip_results)
    zip_count = len(zip_results)

    logger.info(
        f"_build_summary: {len(zip_results)} ZIP results, total_population={total_population}"
    )

    # Calculate weighted averages for summary metrics
    median_income = _weighted_average(zip_results, "income_household_median")
    median_age = await _get_weighted_metric(
        session, "age", "median_age", state_names, county_name, region_name, cbsa_names
    )
    home_ownership = await _get_weighted_metric(
        session, "housing", "home_ownership", state_names, county_name, region_name, cbsa_names
    )

    # Build opportunity bubble chart
    bubble_chart = await _build_bubble_chart(
        session=session,
        state_names=state_names,
        county_name=county_name,
        region_name=region_name,
        cbsa_names=cbsa_names,
    )

    return ReportSummary(
        total_population=total_population,
        zip_count=zip_count,
        median_household_income=median_income,
        median_age=median_age,
        home_ownership_rate=home_ownership,
        narrative=None,  # Can be added via LLM in future
        opportunity_bubble_chart=bubble_chart,
    )


def _weighted_average(
    results: list[AggregatedDemographics],
    column: str,
) -> float | None:
    """Calculate population-weighted average of a column."""
    if not results:
        return None

    weighted_sum = 0.0
    pop_sum = 0.0

    for r in results:
        value = getattr(r, column, None)
        if value is not None and r.population > 0:
            weighted_sum += value * r.population
            pop_sum += r.population

    return weighted_sum / pop_sum if pop_sum > 0 else None


async def _get_weighted_metric(
    session: AsyncSession,
    category: str,
    metric_name: str,
    state_names: list[str] | None,
    county_name: str | None,
    region_name: str | None,
    cbsa_names: list[str] | None,
) -> float | None:
    """Query and calculate weighted average for a single metric."""
    results = await query_aggregated_demographics(
        session=session,
        category=category,
        metric_name=metric_name,
        geography_level=GeographyLevel.ZIP,
        state_names=state_names,
        county_name=county_name,
        region_name=region_name,
        cbsa_names=cbsa_names,
    )

    # Get the column name from the metric config
    metric = DEMOGRAPHICS.get_metric(category, metric_name)
    column = metric.column if metric.column else metric_name

    return _weighted_average(results, column)


async def _build_bubble_chart(
    session: AsyncSession,
    state_names: list[str] | None,
    county_name: str | None,
    region_name: str | None,
    cbsa_names: list[str] | None,
) -> Visualization:
    """Build opportunity bubble chart at ZIP level.

    Defaults:
    - x_axis: median_household_income
    - y_axis: population_density
    - size: population
    - color: home_ownership
    """
    # Query income data at ZIP level (includes population and density)
    results = await query_aggregated_demographics(
        session=session,
        category="income",
        metric_name="median_household_income",
        geography_level=GeographyLevel.ZIP,
        state_names=state_names,
        county_name=county_name,
        region_name=region_name,
        cbsa_names=cbsa_names,
    )

    # Convert to bubble data
    bubble_data = to_bubble_data(
        results=results,
        x_column="income_household_median",
        y_column="density",
        size_column="population",
        color_column="home_ownership",
    )

    logger.info(
        f"_build_bubble_chart: {len(results)} query results -> {len(bubble_data)} bubble points"
    )

    return Visualization(
        visualization_id=str(uuid4()),
        title="Opportunity Matrix",
        subtitle="Income vs Density by Population",
        config=VisualizationConfig(
            chart_type="bubble",
            x_axis_label="Median Household Income ($)",
            y_axis_label="Population Density (per sq mi)",
            size_label="Population",
            color_label="Home Ownership Rate (%)",
        ),
        bubble_data=bubble_data,
    )


async def _build_sections(
    session: AsyncSession,
    target_demographics: list[DemographicTargetRef],
    geography_level: GeographyLevel,
    state_names: list[str] | None,
    county_name: str | None,
    region_name: str | None,
    cbsa_names: list[str] | None,
) -> list[ReportSection]:
    """Build report sections from target demographics.

    Creates one section per target demographic, sorted by importance_weight.
    Each section includes appropriate visualizations based on metric type.
    """
    if not target_demographics:
        return []

    # Sort by importance weight descending
    sorted_targets = sorted(
        target_demographics,
        key=lambda t: t.importance_weight,
        reverse=True,
    )

    sections: list[ReportSection] = []

    for rank, target in enumerate(sorted_targets, start=1):
        section = await _build_section_for_target(
            session=session,
            target=target,
            rank=rank,
            geography_level=geography_level,
            state_names=state_names,
            county_name=county_name,
            region_name=region_name,
            cbsa_names=cbsa_names,
        )
        if section:
            sections.append(section)

    return sections


async def _build_section_for_target(
    session: AsyncSession,
    target: DemographicTargetRef,
    rank: int,
    geography_level: GeographyLevel,
    state_names: list[str] | None,
    county_name: str | None,
    region_name: str | None,
    cbsa_names: list[str] | None,
) -> ReportSection | None:
    """Build a single report section for a demographic target."""
    # Find the category and metric for this demographic key
    category_name, metric_name, metric = _find_metric_for_key(target.demographic_key)
    if not category_name or not metric:
        return None

    category = DEMOGRAPHICS.get_category(category_name)

    # Build visualizations based on metric type
    visualizations: list[Visualization] = []

    if metric.type == MetricType.DISTRIBUTION:
        # Distribution metrics get bar + pie charts
        vis = await _build_distribution_visualization(
            session=session,
            category_name=category_name,
            metric_name=metric_name,
            metric=metric,
            geography_level=geography_level,
            state_names=state_names,
            county_name=county_name,
            region_name=region_name,
            cbsa_names=cbsa_names,
        )
        if vis:
            visualizations.append(vis)

    elif metric.type in (MetricType.PERCENTAGE, MetricType.NUMERIC):
        # Percentage/Numeric metrics get violin/histogram at ZIP level
        vis = await _build_numeric_visualization(
            session=session,
            category_name=category_name,
            metric_name=metric_name,
            metric=metric,
            state_names=state_names,
            county_name=county_name,
            region_name=region_name,
            cbsa_names=cbsa_names,
        )
        if vis:
            visualizations.append(vis)

    return ReportSection(
        section_id=str(uuid4()),
        title=category.display_name,
        subtitle=_format_target_subtitle(target),
        description=None,
        demographic_category=category_name,
        demographic_key=target.demographic_key,
        importance_weight=target.importance_weight * 100,  # Convert to 0-100 scale
        rank=rank,
        visualizations=visualizations,
    )


def _find_metric_for_key(demographic_key: str):
    """Find category and metric for a demographic key.

    Returns (category_name, metric_name, metric) or (None, None, None).
    """
    for cat_name in DEMOGRAPHICS.get_all_categories():
        category = DEMOGRAPHICS.get_category(cat_name)
        for metric_name, metric in category.metrics.items():
            # Check if key matches the column or is in columns dict
            if metric.column == demographic_key:
                return cat_name, metric_name, metric
            if metric.columns and demographic_key in metric.columns.values():
                return cat_name, metric_name, metric
    return None, None, None


def _format_target_subtitle(target: DemographicTargetRef) -> str:
    """Format a human-readable subtitle for the target."""
    parts = []

    if target.constraint_type == "range":
        if target.min_value is not None:
            parts.append(f"min: {target.min_value}")
        if target.max_value is not None:
            parts.append(f"max: {target.max_value}")
    elif target.constraint_type == "threshold_min" and target.min_value is not None:
        parts.append(f">= {target.min_value}")
    elif target.constraint_type == "threshold_max" and target.max_value is not None:
        parts.append(f"<= {target.max_value}")
    elif target.constraint_type == "percentage" and target.target_percentage is not None:
        op_map = {"gt": ">", "lt": "<", "gte": ">=", "lte": "<=", "eq": "="}
        op = op_map.get(target.percentage_operator or "gte", ">=")
        parts.append(f"{op} {target.target_percentage}%")

    return ", ".join(parts) if parts else "Target Analysis"


async def _build_distribution_visualization(
    session: AsyncSession,
    category_name: str,
    metric_name: str,
    metric,
    geography_level: GeographyLevel,
    state_names: list[str] | None,
    county_name: str | None,
    region_name: str | None,
    cbsa_names: list[str] | None,
) -> Visualization | None:
    """Build bar chart visualization for distribution metrics."""
    if not metric.columns:
        return None

    # Query aggregated data
    results = await query_aggregated_demographics(
        session=session,
        category=category_name,
        metric_name=metric_name,
        geography_level=geography_level,
        state_names=state_names,
        county_name=county_name,
        region_name=region_name,
        cbsa_names=cbsa_names,
    )

    if not results:
        return None

    # Build label to column mapping
    value_columns = {
        label.replace("_", " ").title(): col
        for label, col in metric.columns.items()
    }

    categorical_data = to_categorical_data(
        results=results,
        value_columns=value_columns,
    )

    category = DEMOGRAPHICS.get_category(category_name)

    return Visualization(
        visualization_id=str(uuid4()),
        title=f"{category.display_name} Distribution",
        config=VisualizationConfig(
            chart_type="bar",
            x_axis_label="Category",
            y_axis_label="Percentage (%)",
        ),
        categorical_data=categorical_data,
    )


async def _build_numeric_visualization(
    session: AsyncSession,
    category_name: str,
    metric_name: str,
    metric,
    state_names: list[str] | None,
    county_name: str | None,
    region_name: str | None,
    cbsa_names: list[str] | None,
) -> Visualization | None:
    """Build violin/histogram visualization for numeric/percentage metrics."""
    if not metric.column:
        return None

    # Query at ZIP level for granular distribution
    results = await query_aggregated_demographics(
        session=session,
        category=category_name,
        metric_name=metric_name,
        geography_level=GeographyLevel.ZIP,
        state_names=state_names,
        county_name=county_name,
        region_name=region_name,
        cbsa_names=cbsa_names,
    )

    if not results:
        return None

    distribution_data = to_distribution_data(
        results=results,
        value_column=metric.column,
    )

    category = DEMOGRAPHICS.get_category(category_name)

    # Determine appropriate chart type and labels
    if metric.type == MetricType.PERCENTAGE:
        y_label = "Percentage (%)"
    else:
        y_label = "Value"

    return Visualization(
        visualization_id=str(uuid4()),
        title=f"{category.display_name}: {metric_name.replace('_', ' ').title()}",
        config=VisualizationConfig(
            chart_type="violin",
            x_axis_label="ZIP Code",
            y_axis_label=y_label,
        ),
        distribution_data=distribution_data,
    )
