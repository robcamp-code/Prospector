"""Database schema introspection utilities."""


def read_uszips_schema() -> dict[str, list[str]]:
    """Return uszips table schema grouped by category.

    Returns:
        Dict with categories as keys, each containing list of column names.

    Example:
        {
            "location": ["zip", "lat", "lng", "city", "state_id", "state_name", ...],
            "population": ["population", "density"],
            "age": ["age_median", "age_under_10", "age_10_to_19", ...],
            ...
        }
    """
    return {
        "location": [
            "zip",
            "lat",
            "lng",
            "city",
            "state_id",
            "state_name",
            "zcta",
            "parent_zcta",
            "county_fips",
            "county_name",
            "county_weights",
            "county_names_all",
            "county_fips_all",
            "cbsa_fips",
            "cbsa_name",
            "cbsa_metro",
            "csa_fips",
            "csa_name",
            "metdiv_fips",
            "metdiv_name",
            "region",
            "timezone",
            "imprecise",
            "military",
        ],
        "population": [
            "population",
            "density",
        ],
        "age": [
            "age_median",
            "age_under_10",
            "age_10_to_19",
            "age_20s",
            "age_30s",
            "age_40s",
            "age_50s",
            "age_60s",
            "age_70s",
            "age_over_80",
            "age_over_65",
            "age_18_to_24",
            "age_over_18",
        ],
        "gender": [
            "male",
            "female",
        ],
        "marital": [
            "married",
            "divorced",
            "never_married",
            "widowed",
        ],
        "family": [
            "family_size",
            "family_dual_income",
        ],
        "income": [
            "income_household_median",
            "income_household_under_5",
            "income_household_5_to_10",
            "income_household_10_to_15",
            "income_household_15_to_20",
            "income_household_20_to_25",
            "income_household_25_to_35",
            "income_household_35_to_50",
            "income_household_50_to_75",
            "income_household_75_to_100",
            "income_household_100_to_150",
            "income_household_150_over",
            "income_household_six_figure",
            "income_individual_median",
        ],
        "housing": [
            "home_ownership",
            "housing_units",
            "home_value",
            "rent_median",
            "rent_burden",
        ],
        "education": [
            "education_less_highschool",
            "education_highschool",
            "education_some_college",
            "education_bachelors",
            "education_graduate",
            "education_college_or_above",
            "education_stem_degree",
        ],
        "employment": [
            "labor_force_participation",
            "unemployment_rate",
            "self_employed",
            "farmer",
        ],
        "race": [
            "race_white",
            "race_black",
            "race_asian",
            "race_native",
            "race_pacific",
            "race_other",
            "race_multiple",
            "hispanic",
        ],
        "other": [
            "disabled",
            "poverty",
            "limited_english",
            "commute_time",
            "health_uninsured",
            "veteran",
            "charitable_givers",
        ],
    }
