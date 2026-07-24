"""Happy-path tests for ZIP code aggregation refactor."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import Mapped, mapped_column, DeclarativeBase
from sqlalchemy import String, Double

from src.core.services.zips import get_aggregation, AggregationQueryBuilder
from src.core.services.zips.filters import GeographicFilters
from src.core.services.zips.metrics import MetricColumnBuilder
from src.schemas.aggregation import GeographyLevel


class Base(DeclarativeBase):
    """Test base for models."""

    pass


class MockUSZip(Base):
    """Mock USZip model for aggregation testing."""

    __tablename__ = "uszips_test"

    zip: Mapped[str] = mapped_column(String(5), primary_key=True)
    city: Mapped[str | None] = mapped_column(String(120))
    state_name: Mapped[str | None] = mapped_column(String(50))
    county_name: Mapped[str | None] = mapped_column(String(100))
    cbsa_name: Mapped[str | None] = mapped_column(String(100))
    population: Mapped[float | None] = mapped_column(Double)
    density: Mapped[float | None] = mapped_column(Double)
    income_household_median: Mapped[float | None] = mapped_column(Double)
    race_white: Mapped[float | None] = mapped_column(Double)
    race_black: Mapped[float | None] = mapped_column(Double)
    age_median: Mapped[float | None] = mapped_column(Double)


def test_aggregation_query_builder_composition():
    """Test happy-path: AggregationQueryBuilder composition and validation."""
    from unittest.mock import MagicMock

    # Mock AsyncSession
    session = MagicMock()

    # Create builder with valid inputs
    builder = AggregationQueryBuilder(
        session=session,
        group_by=GeographyLevel.STATE,
        metric_selectors=["income.median_household_income", "race.distribution"],
        sort_by="population",
        sort_dir="desc",
        limit=50,
        offset=0,
        state="New York",
    )

    # Validate builder state
    assert builder.group_by == GeographyLevel.STATE
    assert len(builder.parsed_metrics) == 2
    assert builder.sort_by == "population"
    assert builder.sort_dir == "desc"
    assert builder.limit == 50
    assert builder.offset == 0
    assert builder.filters.state == "New York"

    # Verify statement can be built (though we won't execute it)
    stmt = builder.build_statement()
    assert stmt is not None


@pytest.mark.asyncio
async def test_metric_column_builder():
    """Test MetricColumnBuilder in isolation."""
    builder = MetricColumnBuilder()

    # Add a numeric metric
    labels = builder.add_metric("income", "median_household_income")
    assert len(labels) == 1
    assert "income__median_household_income" in labels[0]

    # Add a distribution metric
    labels = builder.add_metric("race", "distribution")
    assert len(labels) > 1  # Multiple sub-keys (white, black, asian, etc.)
    assert any("race__distribution" in label for label in labels)

    # Get all columns
    all_cols = builder.get_all_columns()
    assert len(all_cols) > 2  # At least the numeric + distribution sub-keys

    # Invalid metric raises error
    with pytest.raises(Exception):
        builder.add_metric("invalid_category", "metric")


def _compiled_sql(stmt) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))


def test_density_filter_sql():
    """min/max_density become ZIP-row WHERE clauses that exclude NULL density."""
    from sqlalchemy import select
    from src.core.database import USZip

    filters = GeographicFilters(min_density=1500.0, max_density=3000.0)
    sql = _compiled_sql(filters.apply_to_statement(select(USZip.zip)))

    assert "density IS NOT NULL" in sql
    assert "density >= 1500.0" in sql
    assert "density < 3000.0" in sql


def test_states_list_filter_sql():
    """states list becomes state_name IN (...)."""
    from sqlalchemy import select
    from src.core.database import USZip

    filters = GeographicFilters(states=["Georgia", "Florida"])
    sql = _compiled_sql(filters.apply_to_statement(select(USZip.zip)))

    assert "state_name IN" in sql
    assert "Georgia" in sql
    assert "Florida" in sql


def test_builder_passes_density_and_states_through():
    """AggregationQueryBuilder forwards states/min_density/max_density filter kwargs."""
    from unittest.mock import MagicMock

    builder = AggregationQueryBuilder(
        session=MagicMock(),
        group_by=GeographyLevel.COUNTY,
        metric_selectors=["income.median_household_income"],
        states=["Georgia"],
        min_density=1500.0,
    )
    assert builder.filters.states == ["Georgia"]
    assert builder.filters.min_density == 1500.0

    sql = _compiled_sql(builder.build_statement())
    assert "state_name IN" in sql
    assert "density >= 1500.0" in sql


def test_unknown_metric_error_lists_valid_selectors():
    """A bad metric guess gets an error naming the valid selectors (regression:
    the agent burned ~10 calls guessing education metric names)."""
    from fastapi import HTTPException
    from src.core.services.zips.aggregation import _parse_metric_selector

    with pytest.raises(HTTPException) as exc_info:
        _parse_metric_selector("education.bachelors_degree_or_higher")
    assert "education.college_or_above" in exc_info.value.detail

    with pytest.raises(HTTPException) as exc_info:
        _parse_metric_selector("ethnicity.hispanic")
    assert "race" in exc_info.value.detail


@pytest.mark.asyncio
async def test_geographic_filters():
    """Test GeographicFilters composition."""
    filters = GeographicFilters(
        state="New York",
        county="New York County",
        city=None,
    )

    assert filters.state == "New York"
    assert filters.county == "New York County"
    assert filters.city is None

    # Verify apply_to_statement is callable (integration tested above)
    from sqlalchemy import select
    from src.core.database import USZip

    stmt = select(USZip.zip)
    filtered_stmt = filters.apply_to_statement(stmt)
    assert filtered_stmt is not None
