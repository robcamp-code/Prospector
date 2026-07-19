"""Integration tests for SQL Analyst queries against live database.

These tests require a running PostgreSQL database with uszips data.
Run with: pytest tests/integration/ -v
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.agents.sql_analyst.tools import (
    AggregatedDemographics,
    query_aggregated_demographics,
)
from src.agents.sql_analyst.utils import GeographyLevel
from src.core.config import get_settings
from src.core.state import DemographicTargetRef


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncSession:
    """Get fresh async database session for each test."""
    settings = get_settings()
    # Create fresh engine for each test to avoid connection pool issues
    engine = create_async_engine(settings.async_database_url, echo=False)
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
    await engine.dispose()


class TestSpanishTutorCulturalCenter:
    """Integration tests for Spanish tutor / cultural immersion center use case.

    Business context: A Spanish tutor expanding into a cultural immersion center
    where Spanish and English speakers can share cultures and learn a second language.

    Key demographics:
    - Hispanic population (potential Spanish-speaking community)
    - Limited English speakers (market for English instruction)
    - Education levels (indicates learning orientation)
    - Population density (urban areas for foot traffic)
    """

    @pytest.mark.asyncio
    async def test_hispanic_population_by_county(self, db_session: AsyncSession):
        """Find counties with high Hispanic populations for community outreach."""
        results = await query_aggregated_demographics(
            session=db_session,
            category="race",
            metric_name="hispanic",
            geography_level=GeographyLevel.COUNTY,
            state_name="Texas",  # High Hispanic population state
            order_by="hispanic",
            order_desc=True,
        )

        assert len(results) > 0, "Should return Texas counties"

        # Verify result structure
        first = results[0]
        assert first.state_name == "Texas"
        assert first.county_name is not None
        assert first.population > 0
        assert hasattr(first, "hispanic"), "Should have hispanic percentage"

        # Top Texas counties should have significant Hispanic population
        assert first.hispanic > 20, "Top Texas county should have >20% Hispanic"

        print(f"\nTop 5 Texas counties by Hispanic population:")
        for r in results[:5]:
            print(f"  {r.county_name}: {r.hispanic:.1f}% Hispanic, pop {r.population:,.0f}")

    @pytest.mark.asyncio
    async def test_limited_english_speakers_by_state(self, db_session: AsyncSession):
        """Find states with high limited-English populations (market for English instruction)."""
        results = await query_aggregated_demographics(
            session=db_session,
            category="language",
            metric_name="limited_english",
            geography_level=GeographyLevel.STATE,
            order_by="limited_english",
            order_desc=True,
        )

        assert len(results) > 0, "Should return states"

        # Verify structure
        first = results[0]
        assert first.state_name is not None
        assert first.population > 0
        assert hasattr(first, "limited_english")

        print(f"\nTop 10 states by limited English speakers:")
        for r in results[:10]:
            print(f"  {r.state_name}: {r.limited_english:.1f}% limited English, pop {r.population:,.0f}")

    @pytest.mark.asyncio
    async def test_education_with_income_filter(self, db_session: AsyncSession):
        """Find educated, middle-class areas for cultural programming."""
        # Target areas with household income >= $60k (can afford classes)
        income_filter = DemographicTargetRef(
            demographic_key="income_household_median",
            constraint_type="threshold_min",
            min_value=60000.0,
        )

        results = await query_aggregated_demographics(
            session=db_session,
            category="education",
            metric_name="college_or_above",
            geography_level=GeographyLevel.COUNTY,
            state_name="California",  # Large diverse state
            demographic_targets=[income_filter],
            order_by="education_college_or_above",
            order_desc=True,
        )

        assert len(results) > 0, "Should return California counties meeting income threshold"

        first = results[0]
        assert first.state_name == "California"
        assert hasattr(first, "education_college_or_above")

        print(f"\nTop 5 California counties by college education (income >= $60k):")
        for r in results[:5]:
            print(f"  {r.county_name}: {r.education_college_or_above:.1f}% college+, pop {r.population:,.0f}")

    @pytest.mark.asyncio
    async def test_region_level_hispanic_population(self, db_session: AsyncSession):
        """Compare Hispanic populations across Southwest region states."""
        results = await query_aggregated_demographics(
            session=db_session,
            category="race",
            metric_name="hispanic",
            geography_level=GeographyLevel.STATE,
            region_name="south",  # Southern states
            order_by="hispanic",
            order_desc=True,
        )

        assert len(results) > 0, "Should return Southern states"

        # All results should be from Southern states
        southern_states = {"Texas", "Oklahoma", "Arkansas", "Louisiana", "Mississippi",
                          "Alabama", "Tennessee", "Kentucky", "West Virginia"}
        for r in results:
            assert r.state_name in southern_states, f"{r.state_name} not in South region"

        print(f"\nSouthern states by Hispanic population:")
        for r in results:
            print(f"  {r.state_name}: {r.hispanic:.1f}% Hispanic, pop {r.population:,.0f}")
