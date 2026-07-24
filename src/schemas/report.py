"""Pydantic models for demographic reports and visualizations."""

from typing import Literal

from pydantic import BaseModel, Field


# =============================================================================
# Visualization Data Points
# =============================================================================


class CategoricalDataPoint(BaseModel):
    """Data point for bar/pie charts (aggregated categorical data)."""

    label: str
    value: float
    percentage: float | None = None
    color: str | None = None


class DistributionDataPoint(BaseModel):
    """Data point for violin/histogram charts (ZIP-level granular data)."""

    geography_id: str  # zip code
    geography_label: str  # city name
    value: float


class BubbleDataPoint(BaseModel):
    """Data point for bubble charts (multi-dimensional geographic data)."""

    geography_id: str
    geography_label: str
    x_value: float
    y_value: float
    size_value: float
    color_value: float | None = None
    metadata: dict = Field(default_factory=dict)


# =============================================================================
# Visualization Configuration
# =============================================================================


class VisualizationConfig(BaseModel):
    """Configuration for chart rendering."""

    chart_type: Literal["bar", "pie", "violin", "histogram", "bubble"]
    x_axis_label: str | None = None
    y_axis_label: str | None = None
    size_label: str | None = None  # bubble only
    color_label: str | None = None  # bubble only


# =============================================================================
# Visualization
# =============================================================================


class Visualization(BaseModel):
    """Complete visualization with config and data.

    Only one of categorical_data, distribution_data, or bubble_data
    should be populated based on chart_type:
    - bar, pie → categorical_data
    - violin, histogram → distribution_data
    - bubble → bubble_data
    """

    visualization_id: str
    title: str
    subtitle: str | None = None
    config: VisualizationConfig
    categorical_data: list[CategoricalDataPoint] | None = None
    distribution_data: list[DistributionDataPoint] | None = None
    bubble_data: list[BubbleDataPoint] | None = None


# =============================================================================
# Report Section
# =============================================================================


class ReportSection(BaseModel):
    """A section of the report focused on a demographic category."""

    section_id: str
    title: str
    subtitle: str | None = None
    description: str | None = None
    demographic_category: str | None = None
    demographic_key: str | None = None
    importance_weight: float = Field(default=50.0, ge=0, le=100)  # 0-100 scale
    rank: int
    visualizations: list[Visualization] = Field(default_factory=list)


# =============================================================================
# Report Outline (planning step — never persisted or returned by the API)
# =============================================================================


class SectionOutline(BaseModel):
    """Planned report section: its heading and what data story it should tell."""

    title: str
    focus: str = Field(
        description=(
            "One or two sentences: the story this section tells and which "
            "query result blocks and metrics it should draw on."
        )
    )


class ReportOutline(BaseModel):
    """Report skeleton produced before any section is written."""

    title: str
    subtitle: str
    sections: list[SectionOutline] = Field(min_length=1, max_length=5)


# =============================================================================
# Report Summary
# =============================================================================


class ReportSummary(BaseModel):
    """Summary statistics and overview for the report."""

    total_population: int
    zip_count: int
    median_household_income: float | None = None
    median_age: float | None = None
    home_ownership_rate: float | None = None
    narrative: str | None = None
    opportunity_bubble_chart: Visualization | None = None


# =============================================================================
# Top-Level Report
# =============================================================================


class Report(BaseModel):
    """Complete demographic report with summary and sections."""

    report_id: str
    title: str
    subtitle: str | None = None
    geography_type: str
    geography_value: str
    client_profile_id: str | None = None
    summary: ReportSummary
    sections: list[ReportSection] = Field(default_factory=list)
    generated_at: str | None = None
