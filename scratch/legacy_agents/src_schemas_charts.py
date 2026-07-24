"""D3-ready chart schemas for demographic visualizations."""

from typing import Literal

from pydantic import BaseModel, Field


class ChartDataPoint(BaseModel):
    """Single data point for D3 charts."""

    label: str
    value: float
    percentage: float
    color: str | None = None


class ChartConfig(BaseModel):
    """Configuration for chart rendering."""

    chart_type: Literal["bar", "pie", "histogram"]
    bound_type: Literal["bounded", "unbounded"] = "bounded"
    x_axis_label: str | None = None
    y_axis_label: str | None = None
    show_mode_toggle: bool = False
    default_display_mode: Literal["percentage", "absolute"] = "percentage"


class Chart(BaseModel):
    """Complete chart with config and data."""

    chart_id: str
    title: str
    config: ChartConfig
    data_points: list[ChartDataPoint]


class DemographicSection(BaseModel):
    """Weighted section for a demographic category."""

    section_id: str
    category: str
    demographic_key: str
    title: str
    subtitle: str | None = None
    description: str | None = None
    importance_weight: float = Field(ge=0, le=100)  # 0-100 for display
    rank: int
    comparison_to_national: float | None = None
    charts: list[Chart]


class OpportunityDataPoint(BaseModel):
    """Data point for opportunity matrix (bubble chart)."""

    zip: str
    city: str
    state: str
    median_household_income: float
    population_density: float
    population: int
    home_ownership: float


class AggregatedStatistics(BaseModel):
    """Summary statistics for a geographic area."""

    total_population: int
    median_household_income: float | None = None
    median_age: float | None = None
    home_ownership_rate: float | None = None
    population_density: float | None = None
    zip_count: int = 0


class DemographicReportData(BaseModel):
    """Complete D3-ready report structure."""

    opportunity_matrix: list[OpportunityDataPoint]
    weighted_sections: list[DemographicSection]
    aggregated_statistics: AggregatedStatistics
    raw_demographic_data: dict = Field(default_factory=dict)
