"""Pytest fixtures for tests."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase


class TestBase(DeclarativeBase):
    """Base class for test models that work with SQLite."""

    pass


# Import and recreate minimal models without PostgreSQL-specific types
from sqlalchemy import Boolean, Double, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class TestUSZip(TestBase):
    """Simplified USZip for SQLite testing."""

    __tablename__ = "uszips"

    zip: Mapped[str] = mapped_column(String(5), primary_key=True)
    lat: Mapped[float | None] = mapped_column(Double)
    lng: Mapped[float | None] = mapped_column(Double)
    city: Mapped[str | None] = mapped_column(String(120))
    state_id: Mapped[str | None] = mapped_column(String(2))
    state_name: Mapped[str | None] = mapped_column(String(50))
    population: Mapped[float | None] = mapped_column(Double)
    density: Mapped[float | None] = mapped_column(Double)
    age_median: Mapped[float | None] = mapped_column(Double)
    income_household_median: Mapped[float | None] = mapped_column(Double)
    home_ownership: Mapped[float | None] = mapped_column(Double)
    education_college_or_above: Mapped[float | None] = mapped_column(Double)
    cbsa_name: Mapped[str | None] = mapped_column(String(100))


class TestClientProfile(TestBase):
    """Simplified ClientProfile for SQLite testing."""

    __tablename__ = "client_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_type: Mapped[str | None] = mapped_column(String(100))
    service_description: Mapped[str | None] = mapped_column(Text)
    target_income_min: Mapped[int | None] = mapped_column(Integer)
    target_income_max: Mapped[int | None] = mapped_column(Integer)
    target_age_min: Mapped[int | None] = mapped_column(Integer)
    target_age_max: Mapped[int | None] = mapped_column(Integer)
    target_home_ownership_min: Mapped[float | None] = mapped_column(Double)
    target_education_min: Mapped[float | None] = mapped_column(Double)


@pytest.fixture
def test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    TestBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
