"""Tests for ZipService."""

import pytest

from tests.conftest import TestUSZip as USZip, TestClientProfile as ClientProfile
from src.services.zip_service import ZipService, haversine_distance


def test_haversine_distance():
    """Test Haversine distance calculation."""
    # Phoenix to Scottsdale (approx 15km)
    dist = haversine_distance(33.4484, -112.0740, 33.4942, -111.9261)
    assert 14000 < dist < 16000


def test_haversine_same_point():
    """Test Haversine distance for same point."""
    dist = haversine_distance(33.4484, -112.0740, 33.4484, -112.0740)
    assert dist == 0


def test_zip_service_get_zips_within_radius(test_db):
    """Test getting ZIPs within a radius."""
    # Add test ZIP codes
    zips = [
        USZip(zip="85001", lat=33.4484, lng=-112.0740, city="Phoenix"),
        USZip(zip="85002", lat=33.4500, lng=-112.0700, city="Phoenix"),
        USZip(zip="85003", lat=33.5000, lng=-112.0000, city="Far Away"),
    ]
    for z in zips:
        test_db.add(z)
    test_db.commit()

    service = ZipService(test_db)
    results = service.get_zips_within_radius(33.4484, -112.0740, 5000)

    # Should find the first two but not the third
    assert len(results) >= 1
    zip_codes = [z.zip for z in results]
    assert "85001" in zip_codes


def test_aggregate_demographics(test_db):
    """Test demographic aggregation."""
    zips = [
        USZip(
            zip="85001",
            population=10000,
            income_household_median=50000,
            age_median=35,
            home_ownership=60,
            education_college_or_above=40,
        ),
        USZip(
            zip="85002",
            population=20000,
            income_household_median=80000,
            age_median=40,
            home_ownership=70,
            education_college_or_above=50,
        ),
    ]
    for z in zips:
        test_db.add(z)
    test_db.commit()

    service = ZipService(test_db)
    summary = service.aggregate_demographics(zips)

    assert summary.total_population == 30000
    assert summary.zip_count == 2
    # Weighted averages
    # Income: (50000*10000 + 80000*20000) / 30000 = 70000
    assert abs(summary.avg_income - 70000) < 1


def test_aggregate_demographics_empty():
    """Test demographic aggregation with empty list."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///:memory:")
    Session = sessionmaker(bind=engine)
    session = Session()

    service = ZipService(session)
    summary = service.aggregate_demographics([])

    assert summary.total_population == 0
    assert summary.zip_count == 0


def test_score_zip(test_db):
    """Test ZIP scoring based on profile."""
    zip_high_income = USZip(
        zip="85001",
        income_household_median=150000,
        age_median=35,
        home_ownership=80,
        education_college_or_above=60,
    )
    zip_low_income = USZip(
        zip="85002",
        income_household_median=30000,
        age_median=25,
        home_ownership=30,
        education_college_or_above=20,
    )

    profile = ClientProfile(
        name="High Income Target",
        target_income_min=100000,
        target_age_min=30,
        target_age_max=45,
        target_home_ownership_min=50,
        target_education_min=40,
    )

    service = ZipService(test_db)
    score_high = service.score_zip(zip_high_income, profile)
    score_low = service.score_zip(zip_low_income, profile)

    # High income ZIP should score higher
    assert score_high > score_low


def test_search_metros(test_db):
    """Test metro area search."""
    zips = [
        USZip(zip="85001", cbsa_name="Phoenix-Mesa-Scottsdale, AZ"),
        USZip(zip="85002", cbsa_name="Phoenix-Mesa-Scottsdale, AZ"),
        USZip(zip="30301", cbsa_name="Atlanta-Sandy Springs-Roswell, GA"),
    ]
    for z in zips:
        test_db.add(z)
    test_db.commit()

    service = ZipService(test_db)
    results = service.search_metros("Phoenix")

    assert len(results) == 1
    assert "Phoenix" in results[0]


def test_get_zips_by_metro(test_db):
    """Test getting ZIPs by metro area."""
    zips = [
        USZip(zip="85001", cbsa_name="Phoenix-Mesa-Scottsdale, AZ"),
        USZip(zip="85002", cbsa_name="Phoenix-Mesa-Scottsdale, AZ"),
        USZip(zip="30301", cbsa_name="Atlanta-Sandy Springs-Roswell, GA"),
    ]
    for z in zips:
        test_db.add(z)
    test_db.commit()

    service = ZipService(test_db)
    results = service.get_zips_by_metro("Phoenix-Mesa-Scottsdale, AZ")

    assert len(results) == 2
    zip_codes = [z.zip for z in results]
    assert "85001" in zip_codes
    assert "85002" in zip_codes
