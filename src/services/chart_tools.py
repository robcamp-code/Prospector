"""Standalone async functions for demographic chart queries.

These functions can be called programmatically without an agent:
- From API endpoints (FastAPI async routes)
- From scripts (CLI tools, batch processing)
- From tests (pytest async fixtures)

All functions return Pydantic models that are D3-ready JSON serializable.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from src.core.database import async_engine, DemographicTarget
from src.schemas.charts import (
    Chart,
    DemographicReportData,
    OpportunityDataPoint,
)
from src.services.demographic_queries import DemographicQueryService, GeographyType


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Create and manage a database session."""
    async with AsyncSession(async_engine) as session:
        yield session


async def get_income_chart(
    geography_type: GeographyType,
    geography_value: str,
    session: AsyncSession | None = None,
) -> Chart:
    """Get income distribution bar chart data for any geography.

    Args:
        geography_type: One of "region", "state", "cbsa", "county", "city", "zip"
        geography_value: The value to filter by (e.g., "Georgia", "East Coast")
        session: Optional database session. If not provided, creates a new one.

    Returns:
        Chart: D3-ready chart data with income distribution

    Example:
        >>> chart = await get_income_chart("state", "Georgia")
        >>> print(chart.model_dump_json(indent=2))
    """
    if session is not None:
        service = DemographicQueryService(session)
        return await service.get_income_distribution(geography_type, geography_value)

    async with get_session() as session:
        service = DemographicQueryService(session)
        return await service.get_income_distribution(geography_type, geography_value)


async def get_age_chart(
    geography_type: GeographyType,
    geography_value: str,
    session: AsyncSession | None = None,
) -> Chart:
    """Get age distribution bar chart data.

    Args:
        geography_type: One of "region", "state", "cbsa", "county", "city", "zip"
        geography_value: The value to filter by

    Returns:
        Chart: D3-ready chart data with age distribution
    """
    if session is not None:
        service = DemographicQueryService(session)
        return await service.get_age_distribution(geography_type, geography_value)

    async with get_session() as session:
        service = DemographicQueryService(session)
        return await service.get_age_distribution(geography_type, geography_value)


async def get_education_chart(
    geography_type: GeographyType,
    geography_value: str,
    session: AsyncSession | None = None,
) -> Chart:
    """Get education attainment bar chart data.

    Args:
        geography_type: One of "region", "state", "cbsa", "county", "city", "zip"
        geography_value: The value to filter by

    Returns:
        Chart: D3-ready chart data with education levels
    """
    if session is not None:
        service = DemographicQueryService(session)
        return await service.get_education_distribution(geography_type, geography_value)

    async with get_session() as session:
        service = DemographicQueryService(session)
        return await service.get_education_distribution(geography_type, geography_value)


async def get_homeownership_chart(
    geography_type: GeographyType,
    geography_value: str,
    session: AsyncSession | None = None,
) -> Chart:
    """Get home ownership pie chart data.

    Args:
        geography_type: One of "region", "state", "cbsa", "county", "city", "zip"
        geography_value: The value to filter by

    Returns:
        Chart: D3-ready pie chart data with owners vs renters
    """
    if session is not None:
        service = DemographicQueryService(session)
        return await service.get_homeownership_distribution(geography_type, geography_value)

    async with get_session() as session:
        service = DemographicQueryService(session)
        return await service.get_homeownership_distribution(geography_type, geography_value)


async def get_race_chart(
    geography_type: GeographyType,
    geography_value: str,
    session: AsyncSession | None = None,
) -> Chart:
    """Get race/ethnicity distribution bar chart data.

    Args:
        geography_type: One of "region", "state", "cbsa", "county", "city", "zip"
        geography_value: The value to filter by

    Returns:
        Chart: D3-ready chart data with race/ethnicity breakdown
    """
    if session is not None:
        service = DemographicQueryService(session)
        return await service.get_race_distribution(geography_type, geography_value)

    async with get_session() as session:
        service = DemographicQueryService(session)
        return await service.get_race_distribution(geography_type, geography_value)


async def get_marital_status_chart(
    geography_type: GeographyType,
    geography_value: str,
    session: AsyncSession | None = None,
) -> Chart:
    """Get marital status pie chart data.

    Args:
        geography_type: One of "region", "state", "cbsa", "county", "city", "zip"
        geography_value: The value to filter by

    Returns:
        Chart: D3-ready pie chart data with marital status distribution
    """
    if session is not None:
        service = DemographicQueryService(session)
        return await service.get_marital_status_distribution(geography_type, geography_value)

    async with get_session() as session:
        service = DemographicQueryService(session)
        return await service.get_marital_status_distribution(geography_type, geography_value)


async def get_opportunity_matrix(
    geography_type: GeographyType,
    geography_value: str,
    limit: int = 20,
    session: AsyncSession | None = None,
) -> list[OpportunityDataPoint]:
    """Get top ZIP codes for bubble chart visualization.

    Args:
        geography_type: One of "region", "state", "cbsa", "county", "city", "zip"
        geography_value: The value to filter by
        limit: Maximum number of ZIP codes to return (default 20)

    Returns:
        list[OpportunityDataPoint]: List of ZIP codes with key metrics
    """
    if session is not None:
        service = DemographicQueryService(session)
        return await service.get_opportunity_matrix(geography_type, geography_value, limit)

    async with get_session() as session:
        service = DemographicQueryService(session)
        return await service.get_opportunity_matrix(geography_type, geography_value, limit)


async def get_full_report(
    geography_type: GeographyType,
    geography_value: str,
    profile_id: str | None = None,
    session: AsyncSession | None = None,
) -> DemographicReportData:
    """Generate complete D3-ready demographic report.

    If a profile_id is provided, uses the ClientProfile's DemographicTargets
    to weight sections by importance. Otherwise uses default weights.

    Args:
        geography_type: One of "region", "state", "cbsa", "county", "city", "zip"
        geography_value: The value to filter by
        profile_id: Optional ClientProfile ID to use for weighting
        session: Optional database session

    Returns:
        DemographicReportData: Complete report with weighted sections,
            opportunity matrix, and aggregated statistics
    """
    async def _execute(session: AsyncSession) -> DemographicReportData:
        # Load importance weights from profile if provided
        importance_weights: dict[str, float] | None = None
        if profile_id is not None:
            result = await session.execute(
                select(DemographicTarget).where(
                    DemographicTarget.client_profile_id == profile_id
                )
            )
            targets = result.scalars().all()

            if targets:
                # Convert 0-1 weights to 0-100 for display
                importance_weights = {
                    t.demographic_key: t.importance_weight * 100 for t in targets
                }

        service = DemographicQueryService(session)
        return await service.get_full_demographic_report(
            geography_type, geography_value, importance_weights
        )

    if session is not None:
        return await _execute(session)

    async with get_session() as session:
        return await _execute(session)


async def get_charts_for_keys(
    geography_type: GeographyType,
    geography_value: str,
    demographic_keys: list[str],
    session: AsyncSession | None = None,
) -> dict[str, Chart]:
    """Get multiple charts by demographic key.

    Args:
        geography_type: One of "region", "state", "cbsa", "county", "city", "zip"
        geography_value: The value to filter by
        demographic_keys: List of keys like ["income", "age", "education"]

    Returns:
        dict[str, Chart]: Mapping of demographic_key to Chart
    """
    async def _execute(session: AsyncSession) -> dict[str, Chart]:
        service = DemographicQueryService(session)

        # Map keys to methods
        key_to_method = {
            "income": service.get_income_distribution,
            "age": service.get_age_distribution,
            "education": service.get_education_distribution,
            "home_ownership": service.get_homeownership_distribution,
            "race": service.get_race_distribution,
            "marital": service.get_marital_status_distribution,
        }

        charts = {}
        for key in demographic_keys:
            if key in key_to_method:
                charts[key] = await key_to_method[key](geography_type, geography_value)

        return charts

    if session is not None:
        return await _execute(session)

    async with get_session() as session:
        return await _execute(session)
