from enum import Enum
from typing import Dict, Literal

from pydantic import BaseModel


class MetricType(str, Enum):
    DISTRIBUTION = "distribution"
    PERCENTAGE = "percentage"
    NUMERIC = "numeric"


class Metric(BaseModel):
    type: MetricType
    column: str | None = None
    columns: Dict[str, str] | None = None


class DemographicCategory(BaseModel):
    display_name: str
    metrics: Dict[str, Metric]


CategoryName = Literal[
    "race",
    "age",
    "employment",
    "marital_status",
    "income",
    "education",
    "housing",
    "health",
    "community",
    "language",
    "transportation",
]


class DemographicMapping(BaseModel):
    categories: Dict[CategoryName, DemographicCategory]

    def get_category(self, category: CategoryName) -> DemographicCategory:
        return self.categories[category]

    def get_all_categories(self) -> list[CategoryName]:
        return list(self.categories.keys())

    def get_metric(self, category: CategoryName, metric: str) -> Metric:
        return self.categories[category].metrics[metric]


DEMOGRAPHICS = DemographicMapping(
    categories={
        "race": DemographicCategory(
            display_name="Race / Ethnicity",
            metrics={
                "distribution": Metric(
                    type=MetricType.DISTRIBUTION,
                    columns={
                        "white": "race_white",
                        "black": "race_black",
                        "asian": "race_asian",
                        "native": "race_native",
                        "pacific": "race_pacific",
                        "other": "race_other",
                        "multiple": "race_multiple",
                    },
                ),
                "hispanic": Metric(
                    type=MetricType.PERCENTAGE,
                    column="hispanic",
                ),
            },
        ),
        "age": DemographicCategory(
            display_name="Age",
            metrics={
                "distribution": Metric(
                    type=MetricType.DISTRIBUTION,
                    columns={
                        "under_10": "age_under_10",
                        "10_to_19": "age_10_to_19",
                        "20s": "age_20s",
                        "30s": "age_30s",
                        "40s": "age_40s",
                        "50s": "age_50s",
                        "60s": "age_60s",
                        "70s": "age_70s",
                        "80_plus": "age_over_80",
                    },
                ),
                "median_age": Metric(
                    type=MetricType.NUMERIC,
                    column="age_median",
                ),
                "over_18": Metric(
                    type=MetricType.PERCENTAGE,
                    column="age_over_18",
                ),
                "over_65": Metric(
                    type=MetricType.PERCENTAGE,
                    column="age_over_65",
                ),
            },
        ),
        "employment": DemographicCategory(
            display_name="Employment",
            metrics={
                "labor_force_participation": Metric(
                    type=MetricType.PERCENTAGE,
                    column="labor_force_participation",
                ),
                "unemployment_rate": Metric(
                    type=MetricType.PERCENTAGE,
                    column="unemployment_rate",
                ),
                "self_employed": Metric(
                    type=MetricType.PERCENTAGE,
                    column="self_employed",
                ),
                "farmer": Metric(
                    type=MetricType.PERCENTAGE,
                    column="farmer",
                ),
            },
        ),
        "marital_status": DemographicCategory(
            display_name="Marital Status",
            metrics={
                "distribution": Metric(
                    type=MetricType.DISTRIBUTION,
                    columns={
                        "married": "married",
                        "divorced": "divorced",
                        "never_married": "never_married",
                        "widowed": "widowed",
                    },
                )
            },
        ),
        "income": DemographicCategory(
            display_name="Household Income",
            metrics={
                "distribution": Metric(
                    type=MetricType.DISTRIBUTION,
                    columns={
                        "under_5k": "income_household_under_5",
                        "5k_to_10k": "income_household_5_to_10",
                        "10k_to_15k": "income_household_10_to_15",
                        "15k_to_20k": "income_household_15_to_20",
                        "20k_to_25k": "income_household_20_to_25",
                        "25k_to_35k": "income_household_25_to_35",
                        "35k_to_50k": "income_household_35_to_50",
                        "50k_to_75k": "income_household_50_to_75",
                        "75k_to_100k": "income_household_75_to_100",
                        "100k_to_150k": "income_household_100_to_150",
                        "150k_plus": "income_household_150_over",
                    },
                ),
                "median_household_income": Metric(
                    type=MetricType.NUMERIC,
                    column="income_household_median",
                ),
                "median_individual_income": Metric(
                    type=MetricType.NUMERIC,
                    column="income_individual_median",
                ),
                "six_figure_households": Metric(
                    type=MetricType.PERCENTAGE,
                    column="income_household_six_figure",
                ),
            },
        ),
        "education": DemographicCategory(
            display_name="Education",
            metrics={
                "distribution": Metric(
                    type=MetricType.DISTRIBUTION,
                    columns={
                        "less_than_high_school": "education_less_highschool",
                        "high_school": "education_highschool",
                        "some_college": "education_some_college",
                        "bachelors": "education_bachelors",
                        "graduate": "education_graduate",
                    },
                ),
                "college_or_above": Metric(
                    type=MetricType.PERCENTAGE,
                    column="education_college_or_above",
                ),
                "stem_degree": Metric(
                    type=MetricType.PERCENTAGE,
                    column="education_stem_degree",
                ),
            },
        ),
        "housing": DemographicCategory(
            display_name="Housing",
            metrics={
                "home_ownership": Metric(
                    type=MetricType.PERCENTAGE,
                    column="home_ownership",
                ),
                "median_home_value": Metric(
                    type=MetricType.NUMERIC,
                    column="home_value",
                ),
                "median_rent": Metric(
                    type=MetricType.NUMERIC,
                    column="rent_median",
                ),
                "rent_burden": Metric(
                    type=MetricType.PERCENTAGE,
                    column="rent_burden",
                ),
                "housing_units": Metric(
                    type=MetricType.NUMERIC,
                    column="housing_units",
                ),
            },
        ),
        "health": DemographicCategory(
            display_name="Health",
            metrics={
                "disabled": Metric(
                    type=MetricType.PERCENTAGE,
                    column="disabled",
                ),
                "uninsured": Metric(
                    type=MetricType.PERCENTAGE,
                    column="health_uninsured",
                ),
            },
        ),
        "community": DemographicCategory(
            display_name="Community",
            metrics={
                "veterans": Metric(
                    type=MetricType.PERCENTAGE,
                    column="veteran",
                ),
                "charitable_givers": Metric(
                    type=MetricType.PERCENTAGE,
                    column="charitable_givers",
                ),
            },
        ),
        "language": DemographicCategory(
            display_name="Language",
            metrics={
                "limited_english": Metric(
                    type=MetricType.PERCENTAGE,
                    column="limited_english",
                ),
            },
        ),
        "transportation": DemographicCategory(
            display_name="Transportation",
            metrics={
                "commute_time": Metric(
                    type=MetricType.NUMERIC,
                    column="commute_time",
                ),
            },
        ),
    }
)