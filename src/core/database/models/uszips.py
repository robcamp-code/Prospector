"""USZip model for ZIP code demographic data."""

from sqlmodel import Field, SQLModel


class USZip(SQLModel, table=True):
    """ZIP code demographic data from Census."""

    __tablename__ = "uszips"

    # Primary key
    zip: str = Field(max_length=5, primary_key=True)

    # Location
    lat: float | None = Field(default=None)
    lng: float | None = Field(default=None)
    city: str | None = Field(default=None, max_length=120)
    state_id: str | None = Field(default=None, max_length=2)
    state_name: str | None = Field(default=None, max_length=50)

    # ZCTA info
    zcta: bool | None = Field(default=None)
    parent_zcta: str | None = Field(default=None, max_length=5)

    # Population
    population: float | None = Field(default=None)
    density: float | None = Field(default=None)

    # County
    county_fips: str | None = Field(default=None, max_length=5)
    county_name: str | None = Field(default=None, max_length=45)
    county_weights: str | None = Field(default=None, max_length=500)
    county_names_all: str | None = Field(default=None, max_length=500)
    county_fips_all: str | None = Field(default=None, max_length=100)

    # Flags
    imprecise: bool | None = Field(default=None)
    military: bool | None = Field(default=None)
    timezone: str | None = Field(default=None, max_length=120)

    # Age demographics
    age_median: float | None = Field(default=None)
    age_under_10: float | None = Field(default=None)
    age_10_to_19: float | None = Field(default=None)
    age_20s: float | None = Field(default=None)
    age_30s: float | None = Field(default=None)
    age_40s: float | None = Field(default=None)
    age_50s: float | None = Field(default=None)
    age_60s: float | None = Field(default=None)
    age_70s: float | None = Field(default=None)
    age_over_80: float | None = Field(default=None)
    age_over_65: float | None = Field(default=None)
    age_18_to_24: float | None = Field(default=None)
    age_over_18: float | None = Field(default=None)

    # Gender
    male: float | None = Field(default=None)
    female: float | None = Field(default=None)

    # Marital status
    married: float | None = Field(default=None)
    divorced: float | None = Field(default=None)
    never_married: float | None = Field(default=None)
    widowed: float | None = Field(default=None)

    # Family
    family_size: float | None = Field(default=None)
    family_dual_income: float | None = Field(default=None)

    # Income
    income_household_median: float | None = Field(default=None)
    income_household_under_5: float | None = Field(default=None)
    income_household_5_to_10: float | None = Field(default=None)
    income_household_10_to_15: float | None = Field(default=None)
    income_household_15_to_20: float | None = Field(default=None)
    income_household_20_to_25: float | None = Field(default=None)
    income_household_25_to_35: float | None = Field(default=None)
    income_household_35_to_50: float | None = Field(default=None)
    income_household_50_to_75: float | None = Field(default=None)
    income_household_75_to_100: float | None = Field(default=None)
    income_household_100_to_150: float | None = Field(default=None)
    income_household_150_over: float | None = Field(default=None)
    income_household_six_figure: float | None = Field(default=None)
    income_individual_median: float | None = Field(default=None)

    # Housing
    home_ownership: float | None = Field(default=None)
    housing_units: float | None = Field(default=None)
    home_value: float | None = Field(default=None)
    rent_median: float | None = Field(default=None)
    rent_burden: float | None = Field(default=None)

    # Education
    education_less_highschool: float | None = Field(default=None)
    education_highschool: float | None = Field(default=None)
    education_some_college: float | None = Field(default=None)
    education_bachelors: float | None = Field(default=None)
    education_graduate: float | None = Field(default=None)
    education_college_or_above: float | None = Field(default=None)
    education_stem_degree: float | None = Field(default=None)

    # Employment
    labor_force_participation: float | None = Field(default=None)
    unemployment_rate: float | None = Field(default=None)
    self_employed: float | None = Field(default=None)
    farmer: float | None = Field(default=None)

    # Race/Ethnicity
    race_white: float | None = Field(default=None)
    race_black: float | None = Field(default=None)
    race_asian: float | None = Field(default=None)
    race_native: float | None = Field(default=None)
    race_pacific: float | None = Field(default=None)
    race_other: float | None = Field(default=None)
    race_multiple: float | None = Field(default=None)
    hispanic: float | None = Field(default=None)

    # Other demographics
    disabled: float | None = Field(default=None)
    poverty: float | None = Field(default=None)
    limited_english: float | None = Field(default=None)
    commute_time: float | None = Field(default=None)
    health_uninsured: float | None = Field(default=None)
    veteran: float | None = Field(default=None)
    charitable_givers: float | None = Field(default=None)

    # Metro area
    cbsa_fips: str | None = Field(default=None, max_length=10)
    cbsa_name: str | None = Field(default=None, max_length=100)
    cbsa_metro: bool | None = Field(default=None)
    csa_fips: str | None = Field(default=None, max_length=10)
    csa_name: str | None = Field(default=None, max_length=100)
    metdiv_fips: str | None = Field(default=None, max_length=10)
    metdiv_name: str | None = Field(default=None, max_length=100)

    # Region (East Coast, West Coast, Midwest, South, Mountain West)
    region: str | None = Field(default=None, max_length=20)
