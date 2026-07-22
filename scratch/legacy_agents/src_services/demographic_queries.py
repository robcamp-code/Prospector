"""Demographic query service for population-weighted aggregations.

This service provides prebuilt queries that return D3-ready chart data.
All queries use population-weighted aggregations for accurate demographic
representation across geographic areas.
"""

import math
from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.schemas.charts import (
    AggregatedStatistics,
    Chart,
    ChartConfig,
    ChartDataPoint,
    DemographicReportData,
    DemographicSection,
    OpportunityDataPoint,
)

GeographyType = Literal["region", "state", "cbsa", "county", "city", "zip"]


class DemographicQueryService:
    """Prebuilt demographic queries returning D3-ready data.

    All methods are async and use population-weighted aggregations.
    """

    # Column mappings for each demographic category
    INCOME_COLUMNS = [
        ("income_household_under_5", "<$5K"),
        ("income_household_5_to_10", "$5K-$10K"),
        ("income_household_10_to_15", "$10K-$15K"),
        ("income_household_15_to_20", "$15K-$20K"),
        ("income_household_20_to_25", "$20K-$25K"),
        ("income_household_25_to_35", "$25K-$35K"),
        ("income_household_35_to_50", "$35K-$50K"),
        ("income_household_50_to_75", "$50K-$75K"),
        ("income_household_75_to_100", "$75K-$100K"),
        ("income_household_100_to_150", "$100K-$150K"),
        ("income_household_150_over", "$150K+"),
    ]

    AGE_COLUMNS = [
        ("age_under_10", "Under 10"),
        ("age_10_to_19", "10-19"),
        ("age_20s", "20s"),
        ("age_30s", "30s"),
        ("age_40s", "40s"),
        ("age_50s", "50s"),
        ("age_60s", "60s"),
        ("age_70s", "70s"),
        ("age_over_80", "80+"),
    ]

    EDUCATION_COLUMNS = [
        ("education_less_highschool", "Less than HS"),
        ("education_highschool", "High School"),
        ("education_some_college", "Some College"),
        ("education_bachelors", "Bachelor's"),
        ("education_graduate", "Graduate"),
    ]

    RACE_COLUMNS = [
        ("race_white", "White"),
        ("race_black", "Black"),
        ("race_asian", "Asian"),
        ("race_native", "Native American"),
        ("race_pacific", "Pacific Islander"),
        ("race_other", "Other"),
        ("race_multiple", "Multiple Races"),
    ]

    MARITAL_COLUMNS = [
        ("married", "Married"),
        ("divorced", "Divorced"),
        ("never_married", "Never Married"),
        ("widowed", "Widowed"),
    ]

    # Chart colors for consistent visualization
    CHART_COLORS = {
        "income": [
            "#f7fcf5", "#e5f5e0", "#c7e9c0", "#a1d99b", "#74c476",
            "#41ab5d", "#238b45", "#006d2c", "#00441b", "#003315", "#002210"
        ],
        "age": [
            "#fff5eb", "#fee6ce", "#fdd0a2", "#fdae6b", "#fd8d3c",
            "#f16913", "#d94801", "#a63603", "#7f2704"
        ],
        "education": ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5", "#08306b"],
        "race": [
            "#8dd3c7", "#ffffb3", "#bebada", "#fb8072",
            "#80b1d3", "#fdb462", "#b3de69"
        ],
        "marital": ["#66c2a5", "#fc8d62", "#8da0cb", "#e78ac3"],
    }

    def __init__(self, session: AsyncSession):
        self.session = session

    def _build_geography_filter(
        self,
        geography_type: GeographyType,
    ) -> str:
        """Build SQL WHERE clause for geography filtering."""
        filters = {
            "region": "region = :geo_value",
            "state": "state_name = :geo_value",
            "cbsa": "cbsa_name = :geo_value",
            "county": "county_name = :geo_value",
            "city": "city = :geo_value",
            "zip": "zip = :geo_value",
        }
        return filters.get(geography_type, "1=1")

    async def _execute_distribution_query(
        self,
        columns: list[tuple[str, str]],
        geography_type: GeographyType,
        geography_value: str,
        colors: list[str] | None = None,
    ) -> tuple[list[ChartDataPoint], float]:
        """Execute a population-weighted distribution query.

        Returns list of data points and total population.
        """
        geo_filter = self._build_geography_filter(geography_type)

        # Build the column aggregations
        col_aggregations = ", ".join(
            f"SUM(population * COALESCE(NULLIF({col}, 'NaN'::float8), 0) / 100.0) AS {col}"
            for col, _ in columns
        )

        query = text(f"""
            WITH area_stats AS (
                SELECT
                    SUM(population) AS total_pop,
                    {col_aggregations}
                FROM uszips
                WHERE {geo_filter}
                  AND population IS NOT NULL
                  AND population > 0
                  AND population != 'NaN'::float8
            )
            SELECT total_pop, {', '.join(col for col, _ in columns)}
            FROM area_stats
        """)

        result = await self.session.execute(query, {"geo_value": geography_value})
        row = result.fetchone()

        if not row or not row.total_pop:
            return [], 0

        data_points = []
        total_pop = row.total_pop if row.total_pop and not math.isnan(row.total_pop) else 0

        for i, (col, label) in enumerate(columns):
            raw_value = getattr(row, col)
            # Handle None and NaN values
            value = 0.0 if raw_value is None or (isinstance(raw_value, float) and math.isnan(raw_value)) else float(raw_value)
            percentage = (value / total_pop * 100) if total_pop > 0 else 0.0
            color = colors[i] if colors and i < len(colors) else None
            data_points.append(
                ChartDataPoint(
                    label=label,
                    value=round(value, 0),
                    percentage=round(percentage, 1),
                    color=color,
                )
            )

        return data_points, total_pop

    async def get_income_distribution(
        self,
        geography_type: GeographyType,
        geography_value: str,
    ) -> Chart:
        """Returns bar chart data for income distribution."""
        data_points, _ = await self._execute_distribution_query(
            self.INCOME_COLUMNS,
            geography_type,
            geography_value,
            self.CHART_COLORS["income"],
        )

        return Chart(
            chart_id="chart-income-bar",
            title="Household Income Distribution",
            config=ChartConfig(
                chart_type="bar",
                x_axis_label="Income Range",
                y_axis_label="Percentage of Households",
                show_mode_toggle=True,
            ),
            data_points=data_points,
        )

    async def get_age_distribution(
        self,
        geography_type: GeographyType,
        geography_value: str,
    ) -> Chart:
        """Returns bar chart data for age distribution."""
        data_points, _ = await self._execute_distribution_query(
            self.AGE_COLUMNS,
            geography_type,
            geography_value,
            self.CHART_COLORS["age"],
        )

        return Chart(
            chart_id="chart-age-bar",
            title="Age Distribution",
            config=ChartConfig(
                chart_type="bar",
                x_axis_label="Age Group",
                y_axis_label="Percentage of Population",
                show_mode_toggle=True,
            ),
            data_points=data_points,
        )

    async def get_education_distribution(
        self,
        geography_type: GeographyType,
        geography_value: str,
    ) -> Chart:
        """Returns bar chart data for education attainment."""
        data_points, _ = await self._execute_distribution_query(
            self.EDUCATION_COLUMNS,
            geography_type,
            geography_value,
            self.CHART_COLORS["education"],
        )

        return Chart(
            chart_id="chart-education-bar",
            title="Educational Attainment",
            config=ChartConfig(
                chart_type="bar",
                x_axis_label="Education Level",
                y_axis_label="Percentage of Population",
                show_mode_toggle=True,
            ),
            data_points=data_points,
        )

    async def get_race_distribution(
        self,
        geography_type: GeographyType,
        geography_value: str,
    ) -> Chart:
        """Returns bar chart data for race/ethnicity distribution."""
        data_points, _ = await self._execute_distribution_query(
            self.RACE_COLUMNS,
            geography_type,
            geography_value,
            self.CHART_COLORS["race"],
        )

        return Chart(
            chart_id="chart-race-bar",
            title="Race/Ethnicity Distribution",
            config=ChartConfig(
                chart_type="bar",
                x_axis_label="Race/Ethnicity",
                y_axis_label="Percentage of Population",
                show_mode_toggle=True,
            ),
            data_points=data_points,
        )

    async def get_marital_status_distribution(
        self,
        geography_type: GeographyType,
        geography_value: str,
    ) -> Chart:
        """Returns pie chart data for marital status."""
        data_points, _ = await self._execute_distribution_query(
            self.MARITAL_COLUMNS,
            geography_type,
            geography_value,
            self.CHART_COLORS["marital"],
        )

        return Chart(
            chart_id="chart-marital-pie",
            title="Marital Status",
            config=ChartConfig(
                chart_type="pie",
                show_mode_toggle=False,
            ),
            data_points=data_points,
        )

    async def get_homeownership_distribution(
        self,
        geography_type: GeographyType,
        geography_value: str,
    ) -> Chart:
        """Returns pie chart data for home ownership."""
        geo_filter = self._build_geography_filter(geography_type)

        query = text(f"""
            WITH area_stats AS (
                SELECT
                    SUM(population) AS total_pop,
                    SUM(population * COALESCE(NULLIF(home_ownership, 'NaN'::float8), 0) / 100.0) AS owners
                FROM uszips
                WHERE {geo_filter}
                  AND population IS NOT NULL
                  AND population > 0
                  AND population != 'NaN'::float8
            )
            SELECT
                total_pop,
                owners,
                total_pop - owners AS renters
            FROM area_stats
        """)

        result = await self.session.execute(query, {"geo_value": geography_value})
        row = result.fetchone()

        if not row or not row.total_pop:
            return Chart(
                chart_id="chart-homeownership-pie",
                title="Home Ownership",
                config=ChartConfig(chart_type="pie"),
                data_points=[],
            )

        owner_pct = (row.owners / row.total_pop * 100) if row.total_pop else 0
        renter_pct = 100 - owner_pct

        return Chart(
            chart_id="chart-homeownership-pie",
            title="Home Ownership",
            config=ChartConfig(
                chart_type="pie",
                show_mode_toggle=True,
            ),
            data_points=[
                ChartDataPoint(
                    label="Homeowners",
                    value=round(row.owners, 0),
                    percentage=round(owner_pct, 1),
                    color="#2171b5",
                ),
                ChartDataPoint(
                    label="Renters",
                    value=round(row.renters, 0),
                    percentage=round(renter_pct, 1),
                    color="#6baed6",
                ),
            ],
        )

    async def get_opportunity_matrix(
        self,
        geography_type: GeographyType,
        geography_value: str,
        limit: int = 20,
    ) -> list[OpportunityDataPoint]:
        """Returns top ZIP codes for bubble chart."""
        geo_filter = self._build_geography_filter(geography_type)

        query = text(f"""
            SELECT
                zip,
                city,
                state_id AS state,
                COALESCE(NULLIF(income_household_median, 'NaN'::float8), 0) AS median_household_income,
                COALESCE(NULLIF(density, 'NaN'::float8), 0) AS population_density,
                COALESCE(NULLIF(population, 'NaN'::float8), 0)::int AS population,
                COALESCE(NULLIF(home_ownership, 'NaN'::float8), 0) AS home_ownership
            FROM uszips
            WHERE {geo_filter}
              AND population IS NOT NULL
              AND population != 'NaN'::float8
              AND population > 1000
              AND income_household_median IS NOT NULL
              AND income_household_median != 'NaN'::float8
            ORDER BY population DESC
            LIMIT :limit
        """)

        result = await self.session.execute(
            query, {"geo_value": geography_value, "limit": limit}
        )
        return [OpportunityDataPoint(**dict(row._mapping)) for row in result.fetchall()]

    async def get_aggregated_statistics(
        self,
        geography_type: GeographyType,
        geography_value: str,
    ) -> AggregatedStatistics:
        """Returns summary statistics for a geographic area."""
        geo_filter = self._build_geography_filter(geography_type)

        query = text(f"""
            SELECT
                COALESCE(SUM(population), 0)::int AS total_population,
                COUNT(*) AS zip_count,
                -- Population-weighted median income
                SUM(population * COALESCE(NULLIF(income_household_median, 'NaN'::float8), 0)) /
                    NULLIF(SUM(CASE WHEN income_household_median IS NOT NULL
                                    AND income_household_median != 'NaN'::float8
                               THEN population ELSE 0 END), 0) AS median_household_income,
                -- Population-weighted median age
                SUM(population * COALESCE(NULLIF(age_median, 'NaN'::float8), 0)) /
                    NULLIF(SUM(CASE WHEN age_median IS NOT NULL
                                    AND age_median != 'NaN'::float8
                               THEN population ELSE 0 END), 0) AS median_age,
                -- Population-weighted home ownership
                SUM(population * COALESCE(NULLIF(home_ownership, 'NaN'::float8), 0)) /
                    NULLIF(SUM(CASE WHEN home_ownership IS NOT NULL
                                    AND home_ownership != 'NaN'::float8
                               THEN population ELSE 0 END), 0) AS home_ownership_rate,
                -- Overall density
                SUM(population) / NULLIF(SUM(
                    CASE WHEN density IS NOT NULL AND density > 0
                    THEN population / density ELSE 0 END
                ), 0) AS population_density
            FROM uszips
            WHERE {geo_filter}
              AND population IS NOT NULL
              AND population > 0
              AND population != 'NaN'::float8
        """)

        result = await self.session.execute(query, {"geo_value": geography_value})
        row = result.fetchone()

        if not row:
            return AggregatedStatistics(total_population=0, zip_count=0)

        return AggregatedStatistics(
            total_population=row.total_population or 0,
            median_household_income=round(row.median_household_income, 0) if row.median_household_income else None,
            median_age=round(row.median_age, 1) if row.median_age else None,
            home_ownership_rate=round(row.home_ownership_rate, 1) if row.home_ownership_rate else None,
            population_density=round(row.population_density, 1) if row.population_density else None,
            zip_count=row.zip_count or 0,
        )

    async def get_full_demographic_report(
        self,
        geography_type: GeographyType,
        geography_value: str,
        importance_weights: dict[str, float] | None = None,
    ) -> DemographicReportData:
        """Generates complete D3-ready report with weighted sections.

        Args:
            geography_type: Type of geography filter
            geography_value: Value for geography filter
            importance_weights: Optional dict mapping demographic_key to weight (0-100)
                               e.g., {"income": 90, "age": 75, "education": 60}
        """
        # Default weights if not provided
        if importance_weights is None:
            importance_weights = {
                "income": 80,
                "age": 60,
                "education": 70,
                "home_ownership": 65,
                "race": 50,
                "marital": 40,
            }

        # Fetch all charts
        income_chart = await self.get_income_distribution(geography_type, geography_value)
        age_chart = await self.get_age_distribution(geography_type, geography_value)
        education_chart = await self.get_education_distribution(geography_type, geography_value)
        homeownership_chart = await self.get_homeownership_distribution(geography_type, geography_value)
        race_chart = await self.get_race_distribution(geography_type, geography_value)
        marital_chart = await self.get_marital_status_distribution(geography_type, geography_value)

        # Build sections with weights
        sections_data = [
            ("income", "Income", "income", "Household Income", "Distribution of household income levels", income_chart),
            ("age", "Age", "age", "Age Distribution", "Population breakdown by age groups", age_chart),
            ("education", "Education", "education", "Educational Attainment", "Highest education level achieved", education_chart),
            ("home_ownership", "Housing", "home_ownership", "Home Ownership", "Owner vs renter distribution", homeownership_chart),
            ("race", "Race/Ethnicity", "race", "Race & Ethnicity", "Racial and ethnic composition", race_chart),
            ("marital", "Marital Status", "marital", "Marital Status", "Distribution of marital status", marital_chart),
        ]

        sections = []
        for section_id, category, key, title, description, chart in sections_data:
            weight = importance_weights.get(key, 50)
            sections.append(
                DemographicSection(
                    section_id=f"section-{section_id}",
                    category=category,
                    demographic_key=key,
                    title=title,
                    description=description,
                    importance_weight=weight,
                    rank=0,  # Will be set after sorting
                    charts=[chart],
                )
            )

        # Sort by importance_weight descending and assign ranks
        sections.sort(key=lambda s: s.importance_weight, reverse=True)
        for i, section in enumerate(sections):
            section.rank = i + 1

        # Fetch opportunity matrix and statistics
        opportunity_matrix = await self.get_opportunity_matrix(
            geography_type, geography_value, limit=20
        )
        aggregated_stats = await self.get_aggregated_statistics(
            geography_type, geography_value
        )

        return DemographicReportData(
            opportunity_matrix=opportunity_matrix,
            weighted_sections=sections,
            aggregated_statistics=aggregated_stats,
        )
