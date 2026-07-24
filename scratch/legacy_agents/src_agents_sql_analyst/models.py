"""Pydantic models for SQL Agent LLM structured outputs."""

from pydantic import BaseModel, Field

from src.agents.orchestrator.demographics import CategoryName


class QueryExtraction(BaseModel):
    """LLM output: which metric to query for a demographic category."""

    category: CategoryName
    metric_name: str = Field(
        description="The metric to query (e.g., 'distribution', 'median_age', 'hispanic')"
    )
    order_by_column: str | None = Field(
        default=None,
        description="DEPRECATED: order_by is now derived from metric. This field is ignored.",
    )
    order_desc: bool = Field(
        default=True,
        description="Order descending (highest first) if True",
    )
    reasoning: str = Field(
        description="Brief explanation of why this metric is relevant for the business"
    )


class VisualizationChoice(BaseModel):
    """LLM output: chart type, title, and importance for a category result."""

    chart_type: str = Field(
        description="Chart type: 'bar', 'pie', 'violin', 'histogram', or 'bubble'"
    )
    title: str = Field(description="Human-readable title for the visualization")
    subtitle: str | None = Field(
        default=None,
        description="Optional subtitle with additional context",
    )
    importance_weight: float = Field(
        ge=0,
        le=100,
        description="Importance weight 0-100 based on relevance to business goals",
    )
    reasoning: str = Field(
        description="Brief explanation of why this visualization is valuable"
    )


class CategoryResult(BaseModel):
    """Intermediate result holding extraction, choice, and data summary."""

    category: CategoryName
    extraction: QueryExtraction
    visualization_choice: VisualizationChoice
    row_count: int = Field(description="Number of rows returned from query")
    data_summary: str = Field(
        description="Brief summary of the data (e.g., 'Hispanic: 12.3% to 45.6% across counties')"
    )


class SectionGrouping(BaseModel):
    """LLM output: how to group categories into a report section."""

    section_title: str = Field(description="Title for this section")
    section_description: str = Field(
        description="Brief description of what this section covers"
    )
    category_names: list[CategoryName] = Field(
        description="Categories to include in this section, ordered by importance"
    )


class SectionGroupingResponse(BaseModel):
    """LLM response containing all section groupings."""

    sections: list[SectionGrouping] = Field(
        description="List of section groupings, ordered by importance (most important first)"
    )
    reasoning: str = Field(
        description="Explanation of the grouping logic"
    )


class SummaryNarrative(BaseModel):
    """LLM output: executive summary narrative for the report."""

    headline: str = Field(
        description="One-sentence headline capturing the key opportunity"
    )
    narrative: str = Field(
        description="2-3 paragraph executive summary explaining the market opportunity"
    )
    top_opportunities: list[str] = Field(
        description="3-5 bullet points highlighting top opportunities",
        max_length=5,
    )


class BubbleChartConfig(BaseModel):
    """LLM output: configuration for the opportunity bubble chart."""

    x_metric: str = Field(
        description="Metric for x-axis (e.g., 'hispanic' for Hispanic percentage)"
    )
    x_category: CategoryName = Field(
        description="Category containing x_metric"
    )
    x_label: str = Field(description="Human-readable label for x-axis")
    y_metric: str = Field(
        description="Metric for y-axis (e.g., 'limited_english')"
    )
    y_category: CategoryName = Field(
        description="Category containing y_metric"
    )
    y_label: str = Field(description="Human-readable label for y-axis")
    reasoning: str = Field(
        description="Why these two metrics best represent the market opportunity"
    )
