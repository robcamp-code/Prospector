"""USZip model for ZIP code demographic data."""

from sqlalchemy import Boolean, Double, String
from sqlalchemy.orm import Mapped, mapped_column

from src.v0.models.base import Base


class USZip(Base):
    """ZIP code demographic data from Census."""

    __tablename__ = "uszips"

    # Primary key
    zip: Mapped[str] = mapped_column(String(5), primary_key=True)

    # Location
    lat: Mapped[float | None] = mapped_column(Double)
    lng: Mapped[float | None] = mapped_column(Double)
    city: Mapped[str | None] = mapped_column(String(120))
    state_id: Mapped[str | None] = mapped_column(String(2))
    state_name: Mapped[str | None] = mapped_column(String(50))

    # ZCTA info
    zcta: Mapped[bool | None] = mapped_column(Boolean)
    parent_zcta: Mapped[str | None] = mapped_column(String(5))

    # Population
    population: Mapped[float | None] = mapped_column(Double)
    density: Mapped[float | None] = mapped_column(Double)

    # County
    county_fips: Mapped[str | None] = mapped_column(String(5))
    county_name: Mapped[str | None] = mapped_column(String(45))
    county_weights: Mapped[str | None] = mapped_column(String(500))
    county_names_all: Mapped[str | None] = mapped_column(String(500))
    county_fips_all: Mapped[str | None] = mapped_column(String(100))

    # Flags
    imprecise: Mapped[bool | None] = mapped_column(Boolean)
    military: Mapped[bool | None] = mapped_column(Boolean)
    timezone: Mapped[str | None] = mapped_column(String(120))

    # Age demographics
    age_median: Mapped[float | None] = mapped_column(Double)
    age_under_10: Mapped[float | None] = mapped_column(Double)
    age_10_to_19: Mapped[float | None] = mapped_column(Double)
    age_20s: Mapped[float | None] = mapped_column(Double)
    age_30s: Mapped[float | None] = mapped_column(Double)
    age_40s: Mapped[float | None] = mapped_column(Double)
    age_50s: Mapped[float | None] = mapped_column(Double)
    age_60s: Mapped[float | None] = mapped_column(Double)
    age_70s: Mapped[float | None] = mapped_column(Double)
    age_over_80: Mapped[float | None] = mapped_column(Double)
    age_over_65: Mapped[float | None] = mapped_column(Double)
    age_18_to_24: Mapped[float | None] = mapped_column(Double)
    age_over_18: Mapped[float | None] = mapped_column(Double)

    # Gender
    male: Mapped[float | None] = mapped_column(Double)
    female: Mapped[float | None] = mapped_column(Double)

    # Marital status
    married: Mapped[float | None] = mapped_column(Double)
    divorced: Mapped[float | None] = mapped_column(Double)
    never_married: Mapped[float | None] = mapped_column(Double)
    widowed: Mapped[float | None] = mapped_column(Double)

    # Family
    family_size: Mapped[float | None] = mapped_column(Double)
    family_dual_income: Mapped[float | None] = mapped_column(Double)

    # Income
    income_household_median: Mapped[float | None] = mapped_column(Double)
    income_household_under_5: Mapped[float | None] = mapped_column(Double)
    income_household_5_to_10: Mapped[float | None] = mapped_column(Double)
    income_household_10_to_15: Mapped[float | None] = mapped_column(Double)
    income_household_15_to_20: Mapped[float | None] = mapped_column(Double)
    income_household_20_to_25: Mapped[float | None] = mapped_column(Double)
    income_household_25_to_35: Mapped[float | None] = mapped_column(Double)
    income_household_35_to_50: Mapped[float | None] = mapped_column(Double)
    income_household_50_to_75: Mapped[float | None] = mapped_column(Double)
    income_household_75_to_100: Mapped[float | None] = mapped_column(Double)
    income_household_100_to_150: Mapped[float | None] = mapped_column(Double)
    income_household_150_over: Mapped[float | None] = mapped_column(Double)
    income_household_six_figure: Mapped[float | None] = mapped_column(Double)
    income_individual_median: Mapped[float | None] = mapped_column(Double)

    # Housing
    home_ownership: Mapped[float | None] = mapped_column(Double)
    housing_units: Mapped[float | None] = mapped_column(Double)
    home_value: Mapped[float | None] = mapped_column(Double)
    rent_median: Mapped[float | None] = mapped_column(Double)
    rent_burden: Mapped[float | None] = mapped_column(Double)

    # Education
    education_less_highschool: Mapped[float | None] = mapped_column(Double)
    education_highschool: Mapped[float | None] = mapped_column(Double)
    education_some_college: Mapped[float | None] = mapped_column(Double)
    education_bachelors: Mapped[float | None] = mapped_column(Double)
    education_graduate: Mapped[float | None] = mapped_column(Double)
    education_college_or_above: Mapped[float | None] = mapped_column(Double)
    education_stem_degree: Mapped[float | None] = mapped_column(Double)

    # Employment
    labor_force_participation: Mapped[float | None] = mapped_column(Double)
    unemployment_rate: Mapped[float | None] = mapped_column(Double)
    self_employed: Mapped[float | None] = mapped_column(Double)
    farmer: Mapped[float | None] = mapped_column(Double)

    # Race/Ethnicity
    race_white: Mapped[float | None] = mapped_column(Double)
    race_black: Mapped[float | None] = mapped_column(Double)
    race_asian: Mapped[float | None] = mapped_column(Double)
    race_native: Mapped[float | None] = mapped_column(Double)
    race_pacific: Mapped[float | None] = mapped_column(Double)
    race_other: Mapped[float | None] = mapped_column(Double)
    race_multiple: Mapped[float | None] = mapped_column(Double)
    hispanic: Mapped[float | None] = mapped_column(Double)

    # Other demographics
    disabled: Mapped[float | None] = mapped_column(Double)
    poverty: Mapped[float | None] = mapped_column(Double)
    limited_english: Mapped[float | None] = mapped_column(Double)
    commute_time: Mapped[float | None] = mapped_column(Double)
    health_uninsured: Mapped[float | None] = mapped_column(Double)
    veteran: Mapped[float | None] = mapped_column(Double)
    charitable_givers: Mapped[float | None] = mapped_column(Double)

    # Metro area
    cbsa_fips: Mapped[str | None] = mapped_column(String(10))
    cbsa_name: Mapped[str | None] = mapped_column(String(100))
    cbsa_metro: Mapped[bool | None] = mapped_column(Boolean)
    csa_fips: Mapped[str | None] = mapped_column(String(10))
    csa_name: Mapped[str | None] = mapped_column(String(100))
    metdiv_fips: Mapped[str | None] = mapped_column(String(10))
    metdiv_name: Mapped[str | None] = mapped_column(String(100))
