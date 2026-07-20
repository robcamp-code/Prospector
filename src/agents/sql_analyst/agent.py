"""SQL Agent - LLM-driven demographic report generation.

This agent uses an LLM to dynamically build reports based on business category,
rather than using hardcoded visualization logic. The LLM determines which
demographics are relevant and how to visualize them.

Architecture: Simple async pipeline (not StateGraph) since the flow is linear:
    for category in selected_categories:   # relevant subset, run concurrently
        extract_query(LLM) -> execute_query(DB) -> rank_and_visualize(LLM)
    group_sections(LLM) -> finalize_report(LLM)
"""

import asyncio
import uuid
from datetime import datetime, timezone

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.orchestrator.demographics import DEMOGRAPHICS, CategoryName, MetricType
from src.agents.sql_analyst.models import (
    BubbleChartConfig,
    CategoryResult,
    QueryExtraction,
    SectionGrouping,
    SectionGroupingResponse,
    SummaryNarrative,
    VisualizationChoice,
)
from src.agents.sql_analyst.prompts import (
    BUBBLE_CHART_CONFIG_PROMPT,
    QUERY_EXTRACTION_PROMPT,
    SECTION_GROUPING_PROMPT,
    SUMMARY_NARRATIVE_PROMPT,
    VISUALIZATION_RANKING_PROMPT,
)
from src.agents.sql_analyst.tools import AggregatedDemographics, query_aggregated_demographics
from src.agents.sql_analyst.utils import GeographyLevel, drill_down_level
from src.core.config import get_settings
from src.core.logging import get_logger, timed
from src.core.state import ClientProfileRef, DemographicTargetRef
from src.schemas.report import (
    BubbleDataPoint,
    CategoricalDataPoint,
    Report,
    ReportSection,
    ReportSummary,
    Visualization,
    VisualizationConfig,
)

logger = get_logger(__name__)

# Categories always included for report context, regardless of targets
CORE_CATEGORIES: tuple[CategoryName, ...] = ("income", "age", "education")
# Padding order when targets map to fewer than MIN_CATEGORIES categories
PAD_PRIORITY: tuple[CategoryName, ...] = (
    "housing",
    "employment",
    "race",
    "community",
    "health",
)
MIN_CATEGORIES = 5
# Max concurrent category tasks (each makes 2 LLM calls); lower if 429s appear
CATEGORY_CONCURRENCY = 3


def select_categories(
    targets: list[DemographicTargetRef] | None,
) -> list[CategoryName]:
    """Select which demographic categories to analyze for this client.

    Maps each target's demographic_key (metric key or column name) to its
    category, unions with CORE_CATEGORIES, and pads to MIN_CATEGORIES so
    the report still has enough material for top_n_sections. Falls back to
    all 11 categories when no target maps.
    """
    mapped = {
        cat
        for t in (targets or [])
        if (cat := DEMOGRAPHICS.category_for_metric(t.demographic_key))
    }
    if not mapped:
        return DEMOGRAPHICS.get_all_categories()

    selected = mapped | set(CORE_CATEGORIES)
    for cat in PAD_PRIORITY:
        if len(selected) >= MIN_CATEGORIES:
            break
        selected.add(cat)

    # Canonical DEMOGRAPHICS order keeps report ordering deterministic
    return [c for c in DEMOGRAPHICS.get_all_categories() if c in selected]


def geo_label(r: AggregatedDemographics) -> str:
    """Human-readable label for a query row, most specific geography first.

    Also used as the join key when combining rows from separate queries
    (e.g. the bubble chart), so it must be unique per row: county rows
    need "County, State" — bare state_name would collide across counties.
    """
    return (
        r.cbsa_name
        or (f"{r.county_name}, {r.state_name}" if r.county_name else r.state_name)
        or r.zip
        or "Unknown"
    )


def resolve_metric_name(category: CategoryName, name: str) -> str | None:
    """Resolve an LLM-provided metric name to a valid metric key.

    The LLM sometimes returns the SQL column name (e.g. 'health_uninsured')
    instead of the metric key ('uninsured'), so fall back to matching columns.
    Returns None if the name cannot be resolved.
    """
    metrics = DEMOGRAPHICS.get_category(category).metrics
    if name in metrics:
        return name
    for metric_name, metric in metrics.items():
        if metric.column == name:
            return metric_name
        if metric.columns and name in metric.columns.values():
            return metric_name
    return None


class SQLAgent:
    """LLM-driven SQL agent for demographic report generation."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.llm = init_chat_model(get_settings().model)
        # An AsyncSession cannot be used concurrently; category tasks run in
        # parallel for their LLM calls, so all DB access (queries AND
        # rollbacks) must be serialized behind this lock.
        self._db_lock = asyncio.Lock()

    async def _locked_query(self, step: str, **query_kwargs) -> list[AggregatedDemographics]:
        """Run query_aggregated_demographics serialized behind the session lock.

        On failure, rolls back within the same lock hold so the failed
        transaction can never race a concurrent query on the shared session.
        """
        async with self._db_lock:
            try:
                with timed(step):
                    return await query_aggregated_demographics(
                        session=self.session, **query_kwargs
                    )
            except Exception:
                await self.session.rollback()
                raise

    def _format_target_demographics(self, profile: ClientProfileRef) -> str:
        """Format target demographics for prompt context."""
        if not profile.target_demographics:
            return "None specified"

        lines = []
        for target in profile.target_demographics:
            constraint = target.constraint_type
            if constraint == "threshold_min":
                lines.append(f"- {target.demographic_key} >= {target.min_value}")
            elif constraint == "threshold_max":
                lines.append(f"- {target.demographic_key} <= {target.max_value}")
            elif constraint == "range":
                lines.append(
                    f"- {target.demographic_key}: {target.min_value} to {target.max_value}"
                )
            elif constraint == "percentage":
                op = target.percentage_operator or "gte"
                lines.append(f"- {target.demographic_key} {op} {target.target_percentage}%")

        return "\n".join(lines) if lines else "None specified"

    def _format_available_metrics(self, category: CategoryName) -> str:
        """Format available metrics for a category for prompt context."""
        cat = DEMOGRAPHICS.get_category(category)
        lines = []
        for metric_name, metric in cat.metrics.items():
            if metric.type == MetricType.DISTRIBUTION:
                cols = ", ".join(metric.columns.keys()) if metric.columns else ""
                lines.append(f"- {metric_name} (distribution): {cols}")
            else:
                lines.append(f"- {metric_name} ({metric.type.value}): {metric.column}")
        return "\n".join(lines)

    async def process_category(
        self,
        category: CategoryName,
        profile: ClientProfileRef,
        geography_level: GeographyLevel,
        state_names: list[str] | None,
        region_name: str | None,
        cbsa_names: list[str] | None,
        county_name: str | None = None,
    ) -> tuple[CategoryResult, list[AggregatedDemographics]] | None:
        """Process a single demographic category through extraction and visualization.

        Returns the category result along with the query rows used to build it,
        or None if the query fails or returns no results.
        """
        cat_info = DEMOGRAPHICS.get_category(category)

        # Step 1: Extract query parameters using LLM
        extraction_prompt = QUERY_EXTRACTION_PROMPT.format(
            business_name=profile.name or "Unknown",
            business_type=profile.business_type or "Unknown",
            service_description=profile.service_description or "Not provided",
            target_demographics=self._format_target_demographics(profile),
            category_display_name=cat_info.display_name,
            available_metrics=self._format_available_metrics(category),
        )

        extraction_llm = self.llm.with_structured_output(QueryExtraction)
        with timed(f"llm:{category}.extract"):
            extraction: QueryExtraction = await extraction_llm.ainvoke(
                [HumanMessage(content=extraction_prompt)]
            )

        # Resolve LLM metric name (may be a column name) to a valid metric key
        resolved = resolve_metric_name(category, extraction.metric_name)
        if resolved is None:
            logger.warning(
                f"process_category: {category} unresolvable metric "
                f"'{extraction.metric_name}', skipping category"
            )
            return None
        if resolved != extraction.metric_name:
            logger.info(
                f"process_category: {category} resolved metric "
                f"'{extraction.metric_name}' -> '{resolved}'"
            )
            extraction.metric_name = resolved

        # Step 2: Execute query
        # Derive order_by from the metric's column, not the LLM
        # This prevents the LLM from suggesting columns that don't exist in the query
        try:
            metric = DEMOGRAPHICS.get_metric(category, extraction.metric_name)
            if metric.type == MetricType.DISTRIBUTION:
                # For distributions, order by first column
                order_by_col = next(iter(metric.columns.values())) if metric.columns else None
            else:
                order_by_col = metric.column

            print(
                f"process_category: {category} -> metric={extraction.metric_name}, "
                f"order_by={order_by_col}"
            )

            results = await self._locked_query(
                f"db:{category}.query",
                category=category,
                metric_name=extraction.metric_name,
                geography_level=geography_level,
                state_names=state_names,
                county_name=county_name,
                region_name=region_name,
                cbsa_names=cbsa_names,
                demographic_targets=profile.target_demographics,
                order_by=order_by_col,
                order_desc=extraction.order_desc,
            )
        except Exception as e:
            logger.warning(f"process_category: {category} query failed: {e}")
            return None

        if not results:
            logger.warning(f"process_category: {category} returned 0 rows")
            return None

        print(f"process_category: {category} returned {len(results)} rows")

        # Step 3: Rank and visualize using LLM
        data_sample = self._format_data_sample(results[:10], extraction.metric_name, category)
        data_summary = self._summarize_data(results, extraction.metric_name, category)

        viz_prompt = VISUALIZATION_RANKING_PROMPT.format(
            business_name=profile.name or "Unknown",
            business_type=profile.business_type or "Unknown",
            service_description=profile.service_description or "Not provided",
            category_display_name=cat_info.display_name,
            metric_name=extraction.metric_name,
            row_count=len(results),
            data_sample=data_sample,
        )

        viz_llm = self.llm.with_structured_output(VisualizationChoice)
        with timed(f"llm:{category}.visualize"):
            viz_choice: VisualizationChoice = await viz_llm.ainvoke(
                [HumanMessage(content=viz_prompt)]
            )

        print(
            f"process_category: {category} -> chart_type={viz_choice.chart_type}, "
            f"weight={viz_choice.importance_weight}"
        )

        result = CategoryResult(
            category=category,
            extraction=extraction,
            visualization_choice=viz_choice,
            row_count=len(results),
            data_summary=data_summary,
        )
        return result, results

    def _format_data_sample(
        self, results: list[AggregatedDemographics], metric_name: str, category: CategoryName
    ) -> str:
        """Format a sample of query results for the LLM prompt."""
        metric = DEMOGRAPHICS.get_metric(category, metric_name)
        lines = []

        for r in results[:10]:
            geo = geo_label(r)

            # Get metric value(s)
            if metric.type == MetricType.DISTRIBUTION and metric.columns:
                values = []
                for label, col in list(metric.columns.items())[:3]:
                    val = getattr(r, col, None)
                    if val is not None:
                        values.append(f"{label}: {val:.1f}%")
                lines.append(f"- {geo} (pop: {r.population:,.0f}): {', '.join(values)}")
            else:
                col = metric.column
                val = getattr(r, col, None)
                if val is not None:
                    if "income" in col or "value" in col or "rent" in col:
                        lines.append(f"- {geo} (pop: {r.population:,.0f}): ${val:,.0f}")
                    elif "time" in col:
                        lines.append(f"- {geo} (pop: {r.population:,.0f}): {val:.1f} min")
                    else:
                        lines.append(f"- {geo} (pop: {r.population:,.0f}): {val:.1f}%")

        return "\n".join(lines) if lines else "No data available"

    def _summarize_data(
        self, results: list[AggregatedDemographics], metric_name: str, category: CategoryName
    ) -> str:
        """Generate a brief data summary for the category result."""
        if not results:
            return "No data"

        metric = DEMOGRAPHICS.get_metric(category, metric_name)

        if metric.type == MetricType.DISTRIBUTION and metric.columns:
            # Summarize top column
            col = list(metric.columns.values())[0]
            values = [getattr(r, col, 0) or 0 for r in results]
            if values:
                return f"{list(metric.columns.keys())[0]}: {min(values):.1f}% to {max(values):.1f}% across {len(results)} areas"
            return "Distribution data available"
        else:
            col = metric.column
            values = [getattr(r, col, 0) or 0 for r in results]
            if values:
                return f"{col}: {min(values):.1f} to {max(values):.1f} across {len(results)} areas"
            return "Data available"

    async def group_sections(
        self,
        category_results: list[CategoryResult],
        profile: ClientProfileRef,
        target_sections: int = 5,
    ) -> list[SectionGrouping]:
        """Group category results into logical report sections."""
        if not category_results:
            return []

        # Format results summary for prompt
        results_summary = "\n".join(
            f"- {r.category} ({DEMOGRAPHICS.get_category(r.category).display_name}): "
            f"weight={r.visualization_choice.importance_weight}, "
            f"chart={r.visualization_choice.chart_type}, "
            f"summary={r.data_summary}"
            for r in category_results
        )

        prompt = SECTION_GROUPING_PROMPT.format(
            business_name=profile.name or "Unknown",
            business_type=profile.business_type or "Unknown",
            service_description=profile.service_description or "Not provided",
            category_results_summary=results_summary,
            target_sections=target_sections,
        )

        grouping_llm = self.llm.with_structured_output(SectionGroupingResponse)
        with timed("llm:group_sections"):
            response: SectionGroupingResponse = await grouping_llm.ainvoke(
                [HumanMessage(content=prompt)]
            )

        print(
            f"group_sections: Created {len(response.sections)} sections from "
            f"{len(category_results)} categories"
        )

        return response.sections

    async def weighted_stat(
        self,
        category: CategoryName,
        metric_name: str,
        geography_level: GeographyLevel,
        **geography_filters,
    ) -> float | None:
        """Population-weighted average of one metric across the filter area.

        Runs without demographic-target cutoffs so the stat describes the
        whole region. Returns None on query failure or empty results.
        """
        try:
            rows = await self._locked_query(
                f"db:summary.{metric_name}",
                category=category,
                metric_name=metric_name,
                geography_level=geography_level,
                **geography_filters,
            )
        except Exception as e:
            logger.warning(f"weighted_stat: {metric_name} query failed: {e}")
            return None

        total_pop = sum(r.population for r in rows)
        if not rows or total_pop <= 0:
            return None
        col = DEMOGRAPHICS.get_metric(category, metric_name).column
        return sum((getattr(r, col, 0) or 0) * r.population for r in rows) / total_pop

    async def generate_summary(
        self,
        profile: ClientProfileRef,
        sections: list[ReportSection],
        total_population: int,
        area_count: int,
        geography_level: GeographyLevel,
        geography_filter: str,
        query_level: GeographyLevel | None = None,
        state_names: list[str] | None = None,
        county_name: str | None = None,
        region_name: str | None = None,
        cbsa_names: list[str] | None = None,
    ) -> ReportSummary:
        """Generate executive summary with narrative."""
        section_summaries = "\n".join(
            f"- {s.title}: {s.description or 'Key insights available'}"
            for s in sections
        )

        prompt = SUMMARY_NARRATIVE_PROMPT.format(
            business_name=profile.name or "Unknown",
            business_type=profile.business_type or "Unknown",
            service_description=profile.service_description or "Not provided",
            geography_level=geography_level.value,
            geography_filter=geography_filter,
            total_population=total_population,
            area_count=area_count,
            section_summaries=section_summaries,
        )

        narrative_llm = self.llm.with_structured_output(SummaryNarrative)
        stat_level = query_level or geography_level
        geography_filters = dict(
            state_names=state_names,
            county_name=county_name,
            region_name=region_name,
            cbsa_names=cbsa_names,
        )

        # Narrative and the bubble chart are independent - run concurrently.
        # The headline stats share the locked DB session, so they serialize
        # behind it, but each query is sub-second.
        async def _narrative() -> SummaryNarrative:
            with timed("llm:summary_narrative"):
                return await narrative_llm.ainvoke([HumanMessage(content=prompt)])

        narrative, bubble_chart, median_income, median_age, home_ownership = (
            await asyncio.gather(
                _narrative(),
                self._build_bubble_chart(profile, stat_level, **geography_filters),
                self.weighted_stat(
                    "income", "median_household_income", stat_level, **geography_filters
                ),
                self.weighted_stat("age", "median_age", stat_level, **geography_filters),
                self.weighted_stat(
                    "housing", "home_ownership", stat_level, **geography_filters
                ),
            )
        )

        return ReportSummary(
            total_population=total_population,
            zip_count=area_count,
            median_household_income=median_income,
            median_age=median_age,
            home_ownership_rate=home_ownership,
            narrative=f"{narrative.headline}\n\n{narrative.narrative}",
            opportunity_bubble_chart=bubble_chart,
        )

    async def _build_bubble_chart(
        self,
        profile: ClientProfileRef,
        geography_level: GeographyLevel,
        state_names: list[str] | None = None,
        county_name: str | None = None,
        region_name: str | None = None,
        cbsa_names: list[str] | None = None,
    ) -> Visualization | None:
        """Build the opportunity bubble chart based on profile targets."""
        # Use LLM to determine best bubble chart configuration
        metrics_catalog = "\n".join(
            f"- {cat}: {', '.join(DEMOGRAPHICS.get_category(cat).metrics.keys())}"
            for cat in DEMOGRAPHICS.get_all_categories()
        )
        prompt = BUBBLE_CHART_CONFIG_PROMPT.format(
            business_name=profile.name or "Unknown",
            business_type=profile.business_type or "Unknown",
            service_description=profile.service_description or "Not provided",
            target_demographics=self._format_target_demographics(profile),
            category_results_summary=metrics_catalog,
        )

        config_llm = self.llm.with_structured_output(BubbleChartConfig)
        with timed("llm:bubble_chart_config"):
            config: BubbleChartConfig = await config_llm.ainvoke(
                [HumanMessage(content=prompt)]
            )

        print(
            f"_build_bubble_chart: x={config.x_metric}, y={config.y_metric}"
        )

        # Resolve LLM metric names (may be column names) to valid metric keys
        x_metric_name = resolve_metric_name(config.x_category, config.x_metric)
        y_metric_name = resolve_metric_name(config.y_category, config.y_metric)
        if x_metric_name is None or y_metric_name is None:
            logger.warning(
                f"_build_bubble_chart: Unresolvable metrics "
                f"x='{config.x_metric}', y='{config.y_metric}', skipping chart"
            )
            return None
        config.x_metric = x_metric_name
        config.y_metric = y_metric_name

        geography_filters = dict(
            state_names=state_names,
            county_name=county_name,
            region_name=region_name,
            cbsa_names=cbsa_names,
        )

        # Query both metrics (sequential: same locked session, sub-second each)
        try:
            x_results = await self._locked_query(
                "db:bubble_chart.x_query",
                category=config.x_category,
                metric_name=config.x_metric,
                geography_level=geography_level,
                **geography_filters,
            )
            y_results = await self._locked_query(
                "db:bubble_chart.y_query",
                category=config.y_category,
                metric_name=config.y_metric,
                geography_level=geography_level,
                **geography_filters,
            )
        except Exception as e:
            logger.warning(f"_build_bubble_chart: Query failed: {e}")
            return None

        if not x_results or not y_results:
            return None

        # Build lookup for y values
        y_lookup = {}
        y_metric = DEMOGRAPHICS.get_metric(config.y_category, config.y_metric)
        y_col = y_metric.column
        for r in y_results:
            y_lookup[geo_label(r)] = getattr(r, y_col, 0) or 0

        # Build bubble data points
        x_metric = DEMOGRAPHICS.get_metric(config.x_category, config.x_metric)
        x_col = x_metric.column
        bubble_data = []

        for r in x_results[:50]:  # Limit to top 50 geographies
            key = geo_label(r)
            if key == "Unknown" or key not in y_lookup:
                continue

            x_val = getattr(r, x_col, 0) or 0
            y_val = y_lookup[key]

            bubble_data.append(
                BubbleDataPoint(
                    geography_id=key,
                    geography_label=key,
                    x_value=x_val,
                    y_value=y_val,
                    size_value=r.population,
                    metadata={"population": r.population},
                )
            )

        if not bubble_data:
            return None

        return Visualization(
            visualization_id=f"bubble_{uuid.uuid4().hex[:8]}",
            title=f"Market Opportunity: {config.x_label} vs {config.y_label}",
            subtitle="Bubble size represents population",
            config=VisualizationConfig(
                chart_type="bubble",
                x_axis_label=config.x_label,
                y_axis_label=config.y_label,
                size_label="Population",
            ),
            bubble_data=bubble_data,
        )


def metric_axis_label(metric) -> str:
    """Value-axis label derived from the metric (mirrors _format_data_sample)."""
    if metric.type in (MetricType.PERCENTAGE, MetricType.DISTRIBUTION):
        return "Percent"
    col = metric.column or ""
    if "income" in col or "value" in col or "rent" in col:
        return "USD"
    if "time" in col:
        return "Minutes"
    return col.replace("_", " ").title() or "Value"


def build_visualization(
    category_result: CategoryResult,
    results: list[AggregatedDemographics],
) -> Visualization:
    """Build a Visualization from category result and query data."""
    choice = category_result.visualization_choice
    extraction = category_result.extraction
    category = category_result.category
    metric = DEMOGRAPHICS.get_metric(category, extraction.metric_name)

    viz_id = f"viz_{category}_{uuid.uuid4().hex[:8]}"

    # Distribution bars are labeled by demographic bucket; everything else
    # compares geographies. Unsupported chart types fall back to bar.
    chart_type = choice.chart_type if choice.chart_type in ("bar", "pie") else "bar"
    x_label = "Category" if metric.type == MetricType.DISTRIBUTION else "Geography"

    return Visualization(
        visualization_id=viz_id,
        title=choice.title,
        subtitle=choice.subtitle,
        config=VisualizationConfig(
            chart_type=chart_type,
            x_axis_label=x_label if chart_type == "bar" else None,
            y_axis_label=metric_axis_label(metric) if chart_type == "bar" else None,
        ),
        categorical_data=build_categorical_data(results, metric),
    )


def build_categorical_data(
    results: list[AggregatedDemographics],
    metric,
) -> list[CategoricalDataPoint]:
    """Build categorical data points from query results."""
    data_points = []

    if metric.type == MetricType.DISTRIBUTION and metric.columns:
        # Aggregate distribution across all results (population-weighted)
        total_pop = sum(r.population for r in results)
        for label, col in metric.columns.items():
            weighted_sum = sum(
                (getattr(r, col, 0) or 0) * r.population for r in results
            )
            avg_pct = weighted_sum / total_pop if total_pop > 0 else 0
            data_points.append(
                CategoricalDataPoint(
                    label=label.replace("_", " ").title(),
                    value=avg_pct,
                    percentage=avg_pct,
                )
            )
    else:
        # Top-N geography comparison
        col = metric.column
        for r in results[:10]:
            val = getattr(r, col, 0) or 0
            data_points.append(
                CategoricalDataPoint(
                    label=geo_label(r),
                    value=val,
                    percentage=val if "%" in str(col) or val <= 100 else None,
                )
            )

    return data_points


def build_report_sections(
    section_groupings: list[SectionGrouping],
    category_results: list[CategoryResult],
    all_results: dict[CategoryName, list[AggregatedDemographics]],
    top_n_sections: int,
) -> list[ReportSection]:
    """Assemble ReportSections from LLM groupings and query data.

    Deterministic (no LLM): each section's importance_weight is the average
    of its visualizations' importance weights, and only the top N sections
    by that averaged weight are kept, ranked most important first.
    """
    category_result_map = {r.category: r for r in category_results}

    candidates: list[ReportSection] = []
    for grouping in section_groupings:
        visualizations: list[Visualization] = []
        weights: list[float] = []

        for cat_name in grouping.category_names:
            if cat_name in category_result_map and cat_name in all_results:
                cat_result = category_result_map[cat_name]
                visualizations.append(
                    build_visualization(cat_result, all_results[cat_name])
                )
                weights.append(cat_result.visualization_choice.importance_weight)

        if not visualizations:
            continue

        candidates.append(
            ReportSection(
                section_id=f"section_{len(candidates) + 1}",
                title=grouping.section_title,
                description=grouping.section_description,
                importance_weight=sum(weights) / len(weights),
                rank=0,  # assigned after sorting
                visualizations=visualizations,
            )
        )

    # Keep top N sections by averaged importance, most important first
    candidates.sort(key=lambda s: s.importance_weight, reverse=True)
    sections = candidates[:top_n_sections]
    for rank, section in enumerate(sections, start=1):
        section.rank = rank
        section.section_id = f"section_{rank}"

    return sections


async def generate_report(
    session: AsyncSession,
    client_profile: ClientProfileRef,
    geography_level: GeographyLevel = GeographyLevel.STATE,
    state_names: list[str] | None = None,
    county_name: str | None = None,
    region_name: str | None = None,
    cbsa_names: list[str] | None = None,
    top_n_sections: int = 5,
    categories: list[CategoryName] | None = None,
) -> Report:
    """Generate a demographic report using LLM-driven analysis.

    The agent will:
    1. Select categories relevant to the client's targets (see select_categories)
    2. For each category (concurrently), use LLM to select best metric and query data
    3. Rank results by relevance and assign visualization types
    4. Group categories into logical report sections
    5. Generate executive summary with narrative

    Args:
        session: AsyncSession for database access
        client_profile: Client profile with business_category and target_demographics
        geography_level: Aggregation level for queries
        state_names: List of state names to filter by
        county_name: Filter by county
        region_name: Filter by region
        cbsa_names: List of CBSA names to filter by
        top_n_sections: Number of sections to include (default 5)
        categories: Override which categories to analyze (default: derived
            from the profile's target_demographics)

    Returns:
        Complete Report with summary and sections tailored to business category
    """
    agent = SQLAgent(session)

    # Aggregate one level below the geography filter so every chart compares
    # multiple areas — filtering and grouping at the same level returns one
    # row per filtered geography (a single-bar chart). The caller-passed
    # geography_level remains the report's scope label.
    query_level = drill_down_level(
        state_names=state_names,
        county_name=county_name,
        region_name=region_name,
        cbsa_names=cbsa_names,
    )
    print(
        f"generate_report: scope={geography_level.value}, "
        f"query aggregation={query_level.value}"
    )

    if categories is None:
        categories = select_categories(client_profile.target_demographics)
    print(f"generate_report: Processing {len(categories)} categories: {categories}")

    # Step 1: Process categories concurrently (LLM calls overlap; DB access
    # is serialized inside SQLAgent behind its session lock)
    sem = asyncio.Semaphore(CATEGORY_CONCURRENCY)

    async def run_category(
        category: CategoryName,
    ) -> tuple[CategoryResult, list[AggregatedDemographics]] | None:
        async with sem:
            try:
                with timed(f"category:{category}"):
                    return await agent.process_category(
                        category=category,
                        profile=client_profile,
                        geography_level=query_level,
                        state_names=state_names,
                        region_name=region_name,
                        cbsa_names=cbsa_names,
                        county_name=county_name,
                    )
            except Exception as e:
                logger.warning(f"generate_report: category {category} failed: {e}")
                return None

    outcomes = await asyncio.gather(*(run_category(c) for c in categories))

    category_results: list[CategoryResult] = []
    all_results: dict[CategoryName, list[AggregatedDemographics]] = {}
    # gather preserves input order, keeping report ordering deterministic
    for category, outcome in zip(categories, outcomes):
        if outcome:
            result, results = outcome
            category_results.append(result)
            all_results[category] = results

    print(f"generate_report: {len(category_results)} categories returned results")
    if not category_results:
        logger.error(
            "generate_report: ALL categories failed or returned no rows - the "
            "report will have no sections. Check query warnings above (bad "
            "demographic_target keys or overly strict cutoffs are common causes)."
        )

    # Step 2: Group into sections
    section_groupings = await agent.group_sections(
        category_results, client_profile, top_n_sections
    )

    # Step 3: Build report sections with visualizations (deterministic:
    # section importance = average of visualization weights, keep top N)
    sections = build_report_sections(
        section_groupings, category_results, all_results, top_n_sections
    )

    # Step 4: Calculate totals for summary from an UNFILTERED query so the
    # summary reflects the full region, not just areas meeting target cutoffs
    total_population = 0
    area_count = 0
    try:
        population_rows = await agent._locked_query(
            "db:population_totals",
            category="race",
            metric_name="hispanic",
            geography_level=query_level,
            state_names=state_names,
            county_name=county_name,
            region_name=region_name,
            cbsa_names=cbsa_names,
        )
        total_population = int(sum(r.population for r in population_rows))
        area_count = len(population_rows)
    except Exception as e:
        logger.warning(f"generate_report: population totals query failed: {e}")
        if all_results:
            first_results = next(iter(all_results.values()))
            total_population = int(sum(r.population for r in first_results))
            area_count = len(first_results)

    # Build geography filter description
    if state_names:
        geo_filter = f"States: {', '.join(state_names)}"
    elif cbsa_names:
        geo_filter = f"Metro areas: {', '.join(cbsa_names)}"
    elif region_name:
        geo_filter = f"Region: {region_name}"
    else:
        geo_filter = "Nationwide"

    # Step 5: Generate summary
    summary = await agent.generate_summary(
        profile=client_profile,
        sections=sections,
        total_population=total_population,
        area_count=area_count,
        geography_level=geography_level,
        geography_filter=geo_filter,
        query_level=query_level,
        state_names=state_names,
        county_name=county_name,
        region_name=region_name,
        cbsa_names=cbsa_names,
    )

    # Build report
    report = Report(
        report_id=f"report_{uuid.uuid4().hex[:8]}",
        title=f"Market Analysis: {client_profile.name or 'Business'}",
        subtitle=f"Demographic insights for {geo_filter}",
        geography_type=geography_level.value,
        geography_value=geo_filter,
        client_profile_id=client_profile.profile_id,
        summary=summary,
        sections=sections,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    print(
        f"generate_report: Complete - {len(sections)} sections, "
        f"total_pop={total_population:,}, areas={area_count}"
    )

    return report
