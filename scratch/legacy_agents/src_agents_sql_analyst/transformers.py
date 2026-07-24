"""Data transformation functions for converting query results to visualization models."""

from src.agents.sql_analyst.tools import AggregatedDemographics
from src.core.logging import get_logger
from src.schemas.report import (
    BubbleDataPoint,
    CategoricalDataPoint,
    DistributionDataPoint,
)

logger = get_logger(__name__)


# Default color palette for categorical data
DEFAULT_COLORS = [
    "#4E79A7",  # Blue
    "#F28E2B",  # Orange
    "#E15759",  # Red
    "#76B7B2",  # Teal
    "#59A14F",  # Green
    "#EDC948",  # Yellow
    "#B07AA1",  # Purple
    "#FF9DA7",  # Pink
    "#9C755F",  # Brown
    "#BAB0AC",  # Gray
]


def to_categorical_data(
    results: list[AggregatedDemographics],
    value_columns: dict[str, str],
    include_colors: bool = True,
) -> list[CategoricalDataPoint]:
    """Convert aggregated demographics to categorical data points.

    Used for bar and pie charts. Aggregates values across all results
    and calculates percentages.

    Args:
        results: List of AggregatedDemographics from query
        value_columns: Mapping of display label to column name
            e.g., {"White": "race_white", "Black": "race_black"}
        include_colors: Whether to assign colors from default palette

    Returns:
        List of CategoricalDataPoint for visualization
    """
    logger.debug(f"to_categorical_data: {len(results)} results")
    if not results:
        logger.warning("to_categorical_data: Empty results list, returning []")
        return []

    # Sum up total population across all results
    total_population = sum(r.population for r in results)

    data_points: list[CategoricalDataPoint] = []
    color_idx = 0

    for label, column_name in value_columns.items():
        # Calculate weighted average across all geographies
        weighted_sum = 0.0
        pop_sum = 0.0

        for result in results:
            value = getattr(result, column_name, None)
            if value is not None and result.population > 0:
                weighted_sum += value * result.population
                pop_sum += result.population

        # Calculate the weighted average percentage
        avg_percentage = weighted_sum / pop_sum if pop_sum > 0 else 0.0

        # Value is the population count represented by this percentage
        value = (avg_percentage / 100.0) * total_population

        color = DEFAULT_COLORS[color_idx % len(DEFAULT_COLORS)] if include_colors else None
        color_idx += 1

        data_points.append(
            CategoricalDataPoint(
                label=label,
                value=value,
                percentage=avg_percentage,
                color=color,
            )
        )

    return data_points


def to_distribution_data(
    results: list[AggregatedDemographics],
    value_column: str,
) -> list[DistributionDataPoint]:
    """Convert ZIP-level demographics to distribution data points.

    Used for violin and histogram charts. Returns one point per ZIP code
    for granular distribution visualization.

    Args:
        results: List of AggregatedDemographics at ZIP level
        value_column: Column name containing the value to plot

    Returns:
        List of DistributionDataPoint for visualization
    """
    logger.debug(f"to_distribution_data: {len(results)} results")
    if not results:
        logger.warning("to_distribution_data: Empty results list, returning []")

    data_points: list[DistributionDataPoint] = []

    for result in results:
        value = getattr(result, value_column, None)
        if value is None:
            continue

        # Use zip as geography_id, city as label
        geography_id = result.zip or ""
        geography_label = result.city or result.county_name or ""

        data_points.append(
            DistributionDataPoint(
                geography_id=geography_id,
                geography_label=geography_label,
                value=float(value),
            )
        )

    return data_points


def to_bubble_data(
    results: list[AggregatedDemographics],
    x_column: str = "income_household_median",
    y_column: str = "density",
    size_column: str = "population",
    color_column: str | None = "home_ownership",
) -> list[BubbleDataPoint]:
    """Convert demographics to bubble chart data points.

    Default configuration:
    - x_axis: median_household_income
    - y_axis: population_density
    - size: population
    - color: home_ownership

    Args:
        results: List of AggregatedDemographics
        x_column: Column for x-axis value
        y_column: Column for y-axis value
        size_column: Column for bubble size
        color_column: Column for bubble color (optional)

    Returns:
        List of BubbleDataPoint for visualization
    """
    logger.debug(f"to_bubble_data: {len(results)} results")
    if not results:
        logger.warning("to_bubble_data: Empty results list, returning []")
        return []

    data_points: list[BubbleDataPoint] = []
    skipped = 0

    for result in results:
        x_value = getattr(result, x_column, None)
        y_value = getattr(result, y_column, None)
        size_value = getattr(result, size_column, None)

        # Skip if required values are missing
        if x_value is None or y_value is None or size_value is None:
            skipped += 1
            continue

        color_value = getattr(result, color_column, None) if color_column else None

        # Determine geography_id and label based on available fields
        if result.zip:
            geography_id = result.zip
            geography_label = result.city or result.zip
        elif result.county_name:
            geography_id = f"{result.county_name}_{result.state_name}"
            geography_label = f"{result.county_name}, {result.state_name}"
        elif result.state_name:
            geography_id = result.state_name
            geography_label = result.state_name
        else:
            geography_id = "unknown"
            geography_label = "Unknown"

        # Build metadata with additional context
        metadata = {
            "state": result.state_name,
            "county": result.county_name,
            "population": result.population,
        }
        if result.city:
            metadata["city"] = result.city

        data_points.append(
            BubbleDataPoint(
                geography_id=geography_id,
                geography_label=geography_label,
                x_value=float(x_value),
                y_value=float(y_value),
                size_value=float(size_value),
                color_value=float(color_value) if color_value is not None else None,
                metadata=metadata,
            )
        )

    logger.info(f"to_bubble_data: {len(data_points)} points, skipped {skipped}")
    return data_points
