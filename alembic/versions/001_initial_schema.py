"""Initial schema

Revision ID: 001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # uszips table
    op.create_table(
        "uszips",
        sa.Column("zip", sa.String(5), primary_key=True),
        sa.Column("lat", sa.Double()),
        sa.Column("lng", sa.Double()),
        sa.Column("city", sa.String(120)),
        sa.Column("state_id", sa.String(2)),
        sa.Column("state_name", sa.String(50)),
        sa.Column("zcta", sa.Boolean()),
        sa.Column("parent_zcta", sa.String(5)),
        sa.Column("population", sa.Double()),
        sa.Column("density", sa.Double()),
        sa.Column("county_fips", sa.String(5)),
        sa.Column("county_name", sa.String(45)),
        sa.Column("county_weights", sa.String(500)),
        sa.Column("county_names_all", sa.String(500)),
        sa.Column("county_fips_all", sa.String(100)),
        sa.Column("imprecise", sa.Boolean()),
        sa.Column("military", sa.Boolean()),
        sa.Column("timezone", sa.String(120)),
        # Age demographics
        sa.Column("age_median", sa.Double()),
        sa.Column("age_under_10", sa.Double()),
        sa.Column("age_10_to_19", sa.Double()),
        sa.Column("age_20s", sa.Double()),
        sa.Column("age_30s", sa.Double()),
        sa.Column("age_40s", sa.Double()),
        sa.Column("age_50s", sa.Double()),
        sa.Column("age_60s", sa.Double()),
        sa.Column("age_70s", sa.Double()),
        sa.Column("age_over_80", sa.Double()),
        sa.Column("age_over_65", sa.Double()),
        sa.Column("age_18_to_24", sa.Double()),
        sa.Column("age_over_18", sa.Double()),
        # Gender
        sa.Column("male", sa.Double()),
        sa.Column("female", sa.Double()),
        # Marital
        sa.Column("married", sa.Double()),
        sa.Column("divorced", sa.Double()),
        sa.Column("never_married", sa.Double()),
        sa.Column("widowed", sa.Double()),
        # Family
        sa.Column("family_size", sa.Double()),
        sa.Column("family_dual_income", sa.Double()),
        # Income
        sa.Column("income_household_median", sa.Double()),
        sa.Column("income_household_under_5", sa.Double()),
        sa.Column("income_household_5_to_10", sa.Double()),
        sa.Column("income_household_10_to_15", sa.Double()),
        sa.Column("income_household_15_to_20", sa.Double()),
        sa.Column("income_household_20_to_25", sa.Double()),
        sa.Column("income_household_25_to_35", sa.Double()),
        sa.Column("income_household_35_to_50", sa.Double()),
        sa.Column("income_household_50_to_75", sa.Double()),
        sa.Column("income_household_75_to_100", sa.Double()),
        sa.Column("income_household_100_to_150", sa.Double()),
        sa.Column("income_household_150_over", sa.Double()),
        sa.Column("income_household_six_figure", sa.Double()),
        sa.Column("income_individual_median", sa.Double()),
        # Housing
        sa.Column("home_ownership", sa.Double()),
        sa.Column("housing_units", sa.Double()),
        sa.Column("home_value", sa.Double()),
        sa.Column("rent_median", sa.Double()),
        sa.Column("rent_burden", sa.Double()),
        # Education
        sa.Column("education_less_highschool", sa.Double()),
        sa.Column("education_highschool", sa.Double()),
        sa.Column("education_some_college", sa.Double()),
        sa.Column("education_bachelors", sa.Double()),
        sa.Column("education_graduate", sa.Double()),
        sa.Column("education_college_or_above", sa.Double()),
        sa.Column("education_stem_degree", sa.Double()),
        # Employment
        sa.Column("labor_force_participation", sa.Double()),
        sa.Column("unemployment_rate", sa.Double()),
        sa.Column("self_employed", sa.Double()),
        sa.Column("farmer", sa.Double()),
        # Race
        sa.Column("race_white", sa.Double()),
        sa.Column("race_black", sa.Double()),
        sa.Column("race_asian", sa.Double()),
        sa.Column("race_native", sa.Double()),
        sa.Column("race_pacific", sa.Double()),
        sa.Column("race_other", sa.Double()),
        sa.Column("race_multiple", sa.Double()),
        sa.Column("hispanic", sa.Double()),
        # Other
        sa.Column("disabled", sa.Double()),
        sa.Column("poverty", sa.Double()),
        sa.Column("limited_english", sa.Double()),
        sa.Column("commute_time", sa.Double()),
        sa.Column("health_uninsured", sa.Double()),
        sa.Column("veteran", sa.Double()),
        sa.Column("charitable_givers", sa.Double()),
        # Metro
        sa.Column("cbsa_fips", sa.String(10)),
        sa.Column("cbsa_name", sa.String(100)),
        sa.Column("cbsa_metro", sa.Boolean()),
        sa.Column("csa_fips", sa.String(10)),
        sa.Column("csa_name", sa.String(100)),
        sa.Column("metdiv_fips", sa.String(10)),
        sa.Column("metdiv_name", sa.String(100)),
    )

    # Create indexes for common queries
    op.create_index("ix_uszips_cbsa_name", "uszips", ["cbsa_name"])
    op.create_index("ix_uszips_state_id", "uszips", ["state_id"])
    op.create_index("ix_uszips_lat_lng", "uszips", ["lat", "lng"])

    # places table
    op.create_table(
        "places",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("place_id", sa.String(255), unique=True, nullable=False),
        sa.Column("name", sa.String(255)),
        sa.Column("display_name", sa.String(255)),
        sa.Column("primary_type", sa.String(100)),
        sa.Column("types", postgresql.ARRAY(sa.String(100))),
        sa.Column("lat", sa.Double()),
        sa.Column("lng", sa.Double()),
        sa.Column("zip_code", sa.String(5)),
        sa.Column("address", sa.Text()),
        sa.Column("phone", sa.String(50)),
        sa.Column("website", sa.String(500)),
        sa.Column("rating", sa.Double()),
        sa.Column("review_count", sa.Integer()),
        sa.Column("cached_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("raw_json", postgresql.JSONB()),
    )

    op.create_index("ix_places_place_id", "places", ["place_id"])
    op.create_index("ix_places_zip_code", "places", ["zip_code"])
    op.create_index("ix_places_primary_type", "places", ["primary_type"])

    # client_profiles table
    op.create_table(
        "client_profiles",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("business_type", sa.String(100)),
        sa.Column("service_description", sa.Text()),
        sa.Column("target_income_min", sa.Integer()),
        sa.Column("target_income_max", sa.Integer()),
        sa.Column("target_age_min", sa.Integer()),
        sa.Column("target_age_max", sa.Integer()),
        sa.Column("target_home_ownership_min", sa.Double()),
        sa.Column("target_education_min", sa.Double()),
        sa.Column("custom_weights", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
        ),
    )

    # reports table
    op.create_table(
        "reports",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("report_type", sa.String(50), nullable=False),
        sa.Column(
            "profile_id", sa.Integer(), sa.ForeignKey("client_profiles.id")
        ),
        sa.Column("center_lat", sa.Double()),
        sa.Column("center_lng", sa.Double()),
        sa.Column("metro_cbsa", sa.String(100)),
        sa.Column("radius_meters", sa.Integer()),
        sa.Column("html_content", sa.Text()),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("report_metadata", postgresql.JSONB()),
    )

    op.create_index("ix_reports_profile_id", "reports", ["profile_id"])
    op.create_index("ix_reports_report_type", "reports", ["report_type"])


def downgrade() -> None:
    op.drop_table("reports")
    op.drop_table("client_profiles")
    op.drop_table("places")
    op.drop_table("uszips")
