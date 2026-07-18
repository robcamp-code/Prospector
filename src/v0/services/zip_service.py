"""Service for ZIP code demographic data queries."""

import math
from dataclasses import dataclass

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from src.v0.models.profiles import ClientProfile
from src.v0.models.uszips import USZip


@dataclass
class DemographicSummary:
    """Aggregated demographics for a set of ZIP codes."""

    total_population: float
    avg_income: float
    avg_age: float
    avg_home_ownership: float
    avg_education: float
    zip_count: int


# Haversine constants
EARTH_RADIUS_M = 6371000  # meters


def haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance between two points in meters using Haversine formula."""
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return EARTH_RADIUS_M * c


class ZipService:
    """Service for querying ZIP code demographic data."""

    def __init__(self, db: Session):
        self.db = db

    def get_zips_within_radius(
        self, lat: float, lng: float, radius_m: int
    ) -> list[USZip]:
        """Get all ZIP codes within a radius of a point.

        Uses a bounding box pre-filter for performance, then exact Haversine check.

        Args:
            lat: Center latitude
            lng: Center longitude
            radius_m: Radius in meters

        Returns:
            List of USZip objects within the radius
        """
        # Calculate bounding box for pre-filter (rough approximation)
        lat_delta = radius_m / 111000  # ~111km per degree latitude
        lng_delta = radius_m / (111000 * math.cos(math.radians(lat)))

        # Query with bounding box pre-filter
        stmt = select(USZip).where(
            USZip.lat.isnot(None),
            USZip.lng.isnot(None),
            USZip.lat >= lat - lat_delta,
            USZip.lat <= lat + lat_delta,
            USZip.lng >= lng - lng_delta,
            USZip.lng <= lng + lng_delta,
        )

        candidates = self.db.execute(stmt).scalars().all()

        # Filter by exact Haversine distance
        results = []
        for z in candidates:
            if z.lat is not None and z.lng is not None:
                dist = haversine_distance(lat, lng, z.lat, z.lng)
                if dist <= radius_m:
                    results.append(z)

        return results

    def aggregate_demographics(self, zips: list[USZip]) -> DemographicSummary:
        """Calculate population-weighted average demographics for ZIP codes.

        Args:
            zips: List of USZip objects

        Returns:
            DemographicSummary with weighted averages
        """
        if not zips:
            return DemographicSummary(
                total_population=0,
                avg_income=0,
                avg_age=0,
                avg_home_ownership=0,
                avg_education=0,
                zip_count=0,
            )

        total_pop = 0.0
        weighted_income = 0.0
        weighted_age = 0.0
        weighted_home_ownership = 0.0
        weighted_education = 0.0

        for z in zips:
            pop = z.population or 0
            total_pop += pop

            if pop > 0:
                weighted_income += (z.income_household_median or 0) * pop
                weighted_age += (z.age_median or 0) * pop
                weighted_home_ownership += (z.home_ownership or 0) * pop
                weighted_education += (z.education_college_or_above or 0) * pop

        if total_pop == 0:
            return DemographicSummary(
                total_population=0,
                avg_income=0,
                avg_age=0,
                avg_home_ownership=0,
                avg_education=0,
                zip_count=len(zips),
            )

        return DemographicSummary(
            total_population=total_pop,
            avg_income=weighted_income / total_pop,
            avg_age=weighted_age / total_pop,
            avg_home_ownership=weighted_home_ownership / total_pop,
            avg_education=weighted_education / total_pop,
            zip_count=len(zips),
        )

    def search_metros(self, query: str, limit: int = 10) -> list[str]:
        """Search for CBSA metro area names matching a query.

        Args:
            query: Search string (e.g., "Phoenix")
            limit: Maximum results to return

        Returns:
            List of distinct CBSA names matching the query
        """
        stmt = (
            select(USZip.cbsa_name)
            .where(
                USZip.cbsa_name.isnot(None),
                USZip.cbsa_name != "",
                USZip.cbsa_name.ilike(f"%{query}%"),
            )
            .distinct()
            .limit(limit)
        )

        results = self.db.execute(stmt).scalars().all()
        return list(results)

    def get_zips_by_metro(self, cbsa_name: str) -> list[USZip]:
        """Get all ZIP codes in a metro area.

        Args:
            cbsa_name: CBSA metro area name

        Returns:
            List of USZip objects in the metro area
        """
        stmt = select(USZip).where(USZip.cbsa_name == cbsa_name)
        return list(self.db.execute(stmt).scalars().all())

    def score_zip(self, zip_obj: USZip, profile: ClientProfile) -> float:
        """Score a ZIP code based on how well it matches a client profile.

        Args:
            zip_obj: USZip object to score
            profile: ClientProfile defining target demographics

        Returns:
            Score from 0-100, higher is better match
        """
        score = 50.0  # Start at neutral

        # Income scoring
        if profile.target_income_min or profile.target_income_max:
            income = zip_obj.income_household_median or 0
            if profile.target_income_min and income >= profile.target_income_min:
                score += 10
            if profile.target_income_max and income <= profile.target_income_max:
                score += 10
            elif profile.target_income_max and income > profile.target_income_max:
                score -= 5

        # Age scoring (based on age_median and target range)
        if profile.target_age_min or profile.target_age_max:
            age = zip_obj.age_median or 0
            if profile.target_age_min and age >= profile.target_age_min:
                score += 10
            if profile.target_age_max and age <= profile.target_age_max:
                score += 10

        # Home ownership scoring
        if profile.target_home_ownership_min:
            ownership = zip_obj.home_ownership or 0
            if ownership >= profile.target_home_ownership_min:
                score += 10
            else:
                diff = profile.target_home_ownership_min - ownership
                score -= min(diff / 5, 10)

        # Education scoring
        if profile.target_education_min:
            education = zip_obj.education_college_or_above or 0
            if education >= profile.target_education_min:
                score += 10
            else:
                diff = profile.target_education_min - education
                score -= min(diff / 5, 10)

        # Apply custom weights if provided
        if profile.custom_weights:
            for field, weight in profile.custom_weights.items():
                if hasattr(zip_obj, field):
                    val = getattr(zip_obj, field) or 0
                    score += val * weight

        # Clamp to 0-100
        return max(0, min(100, score))

    def rank_zips_for_profile(
        self, zips: list[USZip], profile: ClientProfile
    ) -> list[tuple[USZip, float]]:
        """Rank ZIP codes by their match score for a profile.

        Args:
            zips: List of USZip objects to rank
            profile: ClientProfile defining target demographics

        Returns:
            List of (USZip, score) tuples sorted by score descending
        """
        scored = [(z, self.score_zip(z, profile)) for z in zips]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
