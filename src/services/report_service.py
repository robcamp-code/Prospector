"""Service for generating HTML reports."""

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session

from src.agents.user_persona import UserPersonaAgent
from src.models.profiles import ClientProfile
from src.models.reports import Report
from src.services.places_service import PlacesService
from src.services.zip_service import ZipService


# Template directory
TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


class ReportService:
    """Service for generating location intelligence reports."""

    def __init__(self, db: Session):
        self.db = db
        self.zip_service = ZipService(db)
        self.places_service = PlacesService(db)
        self.user_persona_agent = UserPersonaAgent()
        self.jinja_env = Environment(
            loader=FileSystemLoader(TEMPLATE_DIR),
            autoescape=True,
        )

    def generate_site_selection(
        self,
        profile_id: int,
        cbsa_name: str,
    ) -> Report:
        """Generate a site selection report for a metro area.

        Args:
            profile_id: ID of the client profile
            cbsa_name: CBSA metro area name

        Returns:
            Report object with generated HTML
        """
        # Get profile
        profile = self.db.get(ClientProfile, profile_id)
        if not profile:
            raise ValueError(f"Profile not found: {profile_id}")

        # Get ZIP codes in metro
        zips = self.zip_service.get_zips_by_metro(cbsa_name)
        if not zips:
            raise ValueError(f"No ZIP codes found for metro: {cbsa_name}")

        # Aggregate demographics
        demographics = self.zip_service.aggregate_demographics(zips)

        # Rank ZIPs by profile match
        ranked_zips = self.zip_service.rank_zips_for_profile(zips, profile)

        # Get competitor types if service description provided
        competitor_types = []
        if profile.service_description:
            place_types = self.user_persona_agent.get_place_types_sync(
                profile.service_description
            )
            competitor_types = place_types.competitor_types

        # Render template
        template = self.jinja_env.get_template("site_selection.html")
        html_content = template.render(
            profile=profile,
            metro_name=cbsa_name,
            zip_count=len(zips),
            demographics=demographics,
            ranked_zips=ranked_zips,
            competitor_types=competitor_types,
            generated_at=datetime.utcnow(),
        )

        # Save report
        report = Report(
            report_type="site_selection",
            profile_id=profile_id,
            metro_cbsa=cbsa_name,
            html_content=html_content,
            report_metadata={
                "zip_count": len(zips),
                "total_population": demographics.total_population,
            },
        )
        self.db.add(report)
        self.db.commit()

        return report

    def generate_trade_area(
        self,
        profile_id: int | None,
        lat: float,
        lng: float,
        radius_m: int = 5000,
        address: str | None = None,
    ) -> Report:
        """Generate a trade area report for a location.

        Args:
            profile_id: Optional ID of the client profile
            lat: Center latitude
            lng: Center longitude
            radius_m: Radius in meters
            address: Optional address string for display

        Returns:
            Report object with generated HTML
        """
        # Get profile if provided
        profile = None
        if profile_id:
            profile = self.db.get(ClientProfile, profile_id)

        # Get ZIP codes in radius
        zips = self.zip_service.get_zips_within_radius(lat, lng, radius_m)

        # Aggregate demographics
        demographics = self.zip_service.aggregate_demographics(zips)

        # Calculate income distribution
        income_distribution = self._calculate_income_distribution(zips)

        # Calculate age distribution
        age_distribution = self._calculate_age_distribution(zips)

        # Get business mix
        business_mix = self.places_service.get_business_mix(lat, lng, radius_m)
        max_business_count = max(business_mix.values()) if business_mix else 0

        # Get competitors and complementary businesses if profile provided
        competitors = []
        complementary = []
        if profile and profile.service_description:
            place_types = self.user_persona_agent.get_place_types_sync(
                profile.service_description
            )
            competitors = self.places_service.get_competitors(
                lat, lng, place_types.competitor_types, radius_m
            )
            complementary = self.places_service.get_complementary(
                lat, lng, place_types.complementary_types, radius_m
            )

        # Render template
        template = self.jinja_env.get_template("trade_area.html")
        html_content = template.render(
            profile=profile,
            center_lat=lat,
            center_lng=lng,
            center_address=address,
            radius_meters=radius_m,
            zip_count=len(zips),
            zips=zips,
            demographics=demographics,
            income_distribution=income_distribution,
            age_distribution=age_distribution,
            business_mix=business_mix,
            max_business_count=max_business_count,
            competitors=competitors,
            complementary=complementary,
            generated_at=datetime.utcnow(),
        )

        # Save report
        report = Report(
            report_type="trade_area",
            profile_id=profile_id,
            center_lat=lat,
            center_lng=lng,
            radius_meters=radius_m,
            html_content=html_content,
            report_metadata={
                "zip_count": len(zips),
                "total_population": demographics.total_population,
                "address": address,
            },
        )
        self.db.add(report)
        self.db.commit()

        return report

    def _calculate_income_distribution(self, zips: list) -> dict[str, float]:
        """Calculate weighted income distribution across ZIP codes."""
        total_pop = sum(z.population or 0 for z in zips)
        if total_pop == 0:
            return {}

        distribution = {
            "<$25k": 0,
            "$25-50k": 0,
            "$50-75k": 0,
            "$75-100k": 0,
            "$100k+": 0,
        }

        for z in zips:
            pop = z.population or 0
            weight = pop / total_pop

            # Aggregate income brackets
            under_25 = (
                (z.income_household_under_5 or 0)
                + (z.income_household_5_to_10 or 0)
                + (z.income_household_10_to_15 or 0)
                + (z.income_household_15_to_20 or 0)
                + (z.income_household_20_to_25 or 0)
            )
            range_25_50 = (
                (z.income_household_25_to_35 or 0)
                + (z.income_household_35_to_50 or 0)
            )
            range_50_75 = z.income_household_50_to_75 or 0
            range_75_100 = z.income_household_75_to_100 or 0
            over_100 = z.income_household_six_figure or 0

            distribution["<$25k"] += under_25 * weight
            distribution["$25-50k"] += range_25_50 * weight
            distribution["$50-75k"] += range_50_75 * weight
            distribution["$75-100k"] += range_75_100 * weight
            distribution["$100k+"] += over_100 * weight

        return distribution

    def _calculate_age_distribution(self, zips: list) -> dict[str, float]:
        """Calculate weighted age distribution across ZIP codes."""
        total_pop = sum(z.population or 0 for z in zips)
        if total_pop == 0:
            return {}

        distribution = {
            "Under 20": 0,
            "20-29": 0,
            "30-39": 0,
            "40-49": 0,
            "50-64": 0,
            "65+": 0,
        }

        for z in zips:
            pop = z.population or 0
            weight = pop / total_pop

            distribution["Under 20"] += (
                (z.age_under_10 or 0) + (z.age_10_to_19 or 0)
            ) * weight
            distribution["20-29"] += (z.age_20s or 0) * weight
            distribution["30-39"] += (z.age_30s or 0) * weight
            distribution["40-49"] += (z.age_40s or 0) * weight
            distribution["50-64"] += (
                (z.age_50s or 0) + (z.age_60s or 0)
            ) * weight
            distribution["65+"] += (z.age_over_65 or 0) * weight

        return distribution
