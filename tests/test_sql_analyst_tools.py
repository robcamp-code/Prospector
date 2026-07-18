"""Unit tests for SQL Analyst Agent tools."""

import pytest
from unittest.mock import MagicMock, patch

from src.agents.sql_analyst.models import AnalysisResult, RankedLocation
from src.agents.sql_analyst.tools import (
    _group_zips_by_hierarchy,
    _score_and_rank_group,
    _score_individual_zips,
)
from src.models.profiles import ClientProfile
from src.models.uszips import USZip
from src.services.zip_service import DemographicSummary, ZipService


@pytest.fixture
def mock_zips():
    """Create mock USZip objects for testing."""
    zips = []
    for i in range(5):
        z = MagicMock(spec=USZip)
        z.zip = f"3000{i}"
        z.city = f"City{i}"
        z.state_name = "Georgia"
        z.state_id = "GA"
        z.county_name = f"County{i % 2}"  # 2 counties
        z.cbsa_name = "Atlanta-Sandy Springs-Alpharetta, GA"
        z.population = 10000 * (i + 1)
        z.income_household_median = 50000 + (i * 10000)
        z.age_median = 35 + i
        z.home_ownership = 0.5 + (i * 0.05)
        z.education_college_or_above = 0.3 + (i * 0.05)
        z.lat = 33.0 + i * 0.1
        z.lng = -84.0 + i * 0.1
        zips.append(z)
    return zips


@pytest.fixture
def mock_profile():
    """Create a mock ClientProfile for testing."""
    profile = MagicMock(spec=ClientProfile)
    profile.id = 1
    profile.name = "Test Business"
    profile.business_type = "retail"
    profile.target_income_min = 50000
    profile.target_income_max = 150000
    profile.target_age_min = 25
    profile.target_age_max = 55
    profile.target_home_ownership_min = 0.4
    profile.target_education_min = 0.3
    profile.custom_weights = None
    return profile


class TestGroupZipsByHierarchy:
    """Tests for _group_zips_by_hierarchy function."""

    def test_groups_by_state(self, mock_zips):
        """Test grouping ZIPs by state."""
        groups = _group_zips_by_hierarchy(mock_zips)
        assert "state" in groups
        assert "Georgia" in groups["state"]
        assert len(groups["state"]["Georgia"]) == 5

    def test_groups_by_cbsa(self, mock_zips):
        """Test grouping ZIPs by CBSA."""
        groups = _group_zips_by_hierarchy(mock_zips)
        assert "cbsa" in groups
        assert "Atlanta-Sandy Springs-Alpharetta, GA" in groups["cbsa"]
        assert len(groups["cbsa"]["Atlanta-Sandy Springs-Alpharetta, GA"]) == 5

    def test_groups_by_county(self, mock_zips):
        """Test grouping ZIPs by county."""
        groups = _group_zips_by_hierarchy(mock_zips)
        assert "county" in groups
        # Should have 2 counties (County0 and County1)
        assert len(groups["county"]) == 2

    def test_groups_by_city(self, mock_zips):
        """Test grouping ZIPs by city."""
        groups = _group_zips_by_hierarchy(mock_zips)
        assert "city" in groups
        # Each ZIP has a unique city
        assert len(groups["city"]) == 5

    def test_handles_none_values(self):
        """Test handling of None geographic values."""
        z = MagicMock(spec=USZip)
        z.zip = "30000"
        z.city = None
        z.state_name = None
        z.state_id = None
        z.county_name = None
        z.cbsa_name = None

        groups = _group_zips_by_hierarchy([z])

        assert len(groups["state"]) == 0
        assert len(groups["cbsa"]) == 0
        assert len(groups["county"]) == 0
        assert len(groups["city"]) == 0


class TestScoreAndRankGroup:
    """Tests for _score_and_rank_group function."""

    def test_returns_ranked_locations(self, mock_zips, mock_profile):
        """Test that function returns RankedLocation objects."""
        groups = _group_zips_by_hierarchy(mock_zips)

        with patch.object(ZipService, "score_zip", return_value=75.0):
            with patch.object(
                ZipService,
                "aggregate_demographics",
                return_value=DemographicSummary(
                    total_population=50000,
                    avg_income=75000,
                    avg_age=38,
                    avg_home_ownership=0.65,
                    avg_education=0.45,
                    zip_count=5,
                ),
            ):
                mock_service = MagicMock(spec=ZipService)
                mock_service.score_zip.return_value = 75.0
                mock_service.aggregate_demographics.return_value = DemographicSummary(
                    total_population=50000,
                    avg_income=75000,
                    avg_age=38,
                    avg_home_ownership=0.65,
                    avg_education=0.45,
                    zip_count=5,
                )

                result = _score_and_rank_group(
                    groups["city"], "city", mock_service, mock_profile
                )

                assert len(result) <= 5
                assert all(isinstance(r, RankedLocation) for r in result)
                assert all(r.geo_type == "city" for r in result)

    def test_respects_top_n(self, mock_zips, mock_profile):
        """Test that function respects top_n parameter."""
        groups = _group_zips_by_hierarchy(mock_zips)

        mock_service = MagicMock(spec=ZipService)
        mock_service.score_zip.return_value = 75.0
        mock_service.aggregate_demographics.return_value = DemographicSummary(
            total_population=50000,
            avg_income=75000,
            avg_age=38,
            avg_home_ownership=0.65,
            avg_education=0.45,
            zip_count=5,
        )

        result = _score_and_rank_group(
            groups["city"], "city", mock_service, mock_profile, top_n=3
        )

        assert len(result) <= 3

    def test_ranks_by_score_descending(self, mock_zips, mock_profile):
        """Test that results are ranked by score in descending order."""
        groups = _group_zips_by_hierarchy(mock_zips)

        # Create service with varying scores
        scores = [90, 70, 80, 60, 85]
        score_iter = iter(scores)

        mock_service = MagicMock(spec=ZipService)
        mock_service.score_zip.side_effect = lambda z, p: next(score_iter)
        mock_service.aggregate_demographics.return_value = DemographicSummary(
            total_population=10000,
            avg_income=70000,
            avg_age=35,
            avg_home_ownership=0.6,
            avg_education=0.4,
            zip_count=1,
        )

        result = _score_and_rank_group(
            groups["city"], "city", mock_service, mock_profile
        )

        # Scores should be in descending order
        for i in range(len(result) - 1):
            assert result[i].score >= result[i + 1].score


class TestScoreIndividualZips:
    """Tests for _score_individual_zips function."""

    def test_returns_ranked_locations(self, mock_zips, mock_profile):
        """Test that function returns RankedLocation objects for ZIPs."""
        mock_service = MagicMock(spec=ZipService)
        mock_service.rank_zips_for_profile.return_value = [
            (mock_zips[0], 85.0),
            (mock_zips[1], 80.0),
            (mock_zips[2], 75.0),
        ]

        result = _score_individual_zips(mock_zips, mock_service, mock_profile)

        assert len(result) <= 5
        assert all(isinstance(r, RankedLocation) for r in result)
        assert all(r.geo_type == "zip" for r in result)

    def test_includes_zip_code_in_result(self, mock_zips, mock_profile):
        """Test that ZIP code is included in the result."""
        mock_service = MagicMock(spec=ZipService)
        mock_service.rank_zips_for_profile.return_value = [(mock_zips[0], 85.0)]

        result = _score_individual_zips(mock_zips, mock_service, mock_profile)

        assert len(result) == 1
        assert result[0].zip_codes == ["30000"]


class TestAnalysisResultModel:
    """Tests for AnalysisResult model."""

    def test_creates_valid_analysis_result(self):
        """Test creating a valid AnalysisResult."""
        result = AnalysisResult(
            profile_id=1,
            profile_name="Test Business",
            target_geography="Atlanta-Sandy Springs-Alpharetta, GA",
            geography_type="cbsa",
            top_states=[],
            top_cbsas=[],
            top_counties=[],
            top_cities=[],
            top_zips=[],
            total_zips_analyzed=100,
            total_population=500000,
        )

        assert result.profile_id == 1
        assert result.profile_name == "Test Business"
        assert result.total_zips_analyzed == 100

    def test_ranked_location_model(self):
        """Test creating a valid RankedLocation."""
        loc = RankedLocation(
            rank=1,
            geo_type="county",
            name="Fulton, GA",
            score=85.5,
            population=100000,
            median_income=75000,
            median_age=38,
            home_ownership=0.65,
            education_rate=0.45,
            zip_count=25,
            zip_codes=[],
        )

        assert loc.rank == 1
        assert loc.geo_type == "county"
        assert loc.score == 85.5
