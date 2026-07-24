"""Data Analyst node: turn typed Preferences into a validated QueryPlan.

The plan contains only group_by/metrics/sort/limit — location never appears
in a query; it is injected as WHERE filters by the report generator.
"""

from langchain_core.runnables import RunnableConfig

from src.agents.chat.base import SubAgent
from src.agents.chat.data_analyst import prompts
from src.agents.chat.graph_state import GraphState
from src.core.demographics import DEMOGRAPHICS, MetricType
from src.schemas.aggregation import AggregationQuery, QueryPlan
from src.schemas.preferences import LocationPreference, Preferences, load_preferences

ZIP_ROW_LIMIT = 100  # cap zip-grain queries to keep report-LLM context sane


class DataAnalyst(SubAgent):
    """Plan aggregation queries from preferences via structured output + guardrails."""

    async def __call__(self, state: GraphState, config: RunnableConfig) -> dict:
        preferences = load_preferences(state.get("preferences"))
        if preferences is None:
            # Should not happen (router requires profile_complete); fall back
            # to an empty-preferences plan rather than crashing the thread.
            preferences = Preferences()

        plan_prompt = prompts.QUERY_PLAN_PROMPT.format(
            business_type=preferences.business_type,
            service_description=preferences.service_description,
            price_point=preferences.price_point,
            target_customer_description=preferences.target_customer_description,
            demographic_categories=", ".join(preferences.demographic_categories) or "analyst's choice",
            location_description=(preferences.location or LocationPreference()).describe(),
            metric_catalog=DEMOGRAPHICS.metric_catalog_text(),
        )

        plan = await self.ainvoke_with_retry(
            self.llm.with_structured_output(QueryPlan),
            [{"role": "user", "content": plan_prompt}],
        )

        plan = apply_guardrails(plan, preferences)

        return {"query_plan": plan.model_dump()}


def apply_guardrails(plan: QueryPlan, preferences: Preferences) -> QueryPlan:
    """Deterministically enforce plan rules the LLM might violate.

    - group_by="state" is only allowed for a nationwide scope; otherwise it is
      rewritten to "county" (regression: the east-coast report grouped by state).
    - Queries whose metrics all failed validation are dropped.
    - zip-grain queries are capped at ZIP_ROW_LIMIT rows.
    - A degenerate/empty plan is replaced with a deterministic fallback.
    """
    location = preferences.location
    location_scoped = location is not None and not location.is_nationwide()

    queries = []
    for query in plan.queries:
        if not query.metrics:
            continue
        if location_scoped and query.group_by == "state":
            query = query.model_copy(update={"group_by": "county"})
        if query.group_by == "zip" and query.limit > ZIP_ROW_LIMIT:
            query = query.model_copy(update={"limit": ZIP_ROW_LIMIT})
        queries.append(query)

    if not queries:
        return fallback_plan(preferences)

    return plan.model_copy(update={"queries": queries})


def fallback_plan(preferences: Preferences) -> QueryPlan:
    """Deterministic plan when the LLM produced nothing usable.

    One county-level ranking of headline (non-distribution) metrics and one
    zip-level distribution query, built from the preferred categories.
    """
    categories = list(preferences.demographic_categories) or ["income", "education", "age"]
    for core in ("income", "age"):
        if core not in categories:
            categories.append(core)

    headline_metrics: list[str] = []
    distribution_metrics: list[str] = []
    for category in categories:
        for metric_name, metric in DEMOGRAPHICS.get_category(category).metrics.items():
            selector = f"{category}.{metric_name}"
            if metric.type == MetricType.DISTRIBUTION:
                distribution_metrics.append(selector)
            elif len(headline_metrics) < 6:
                headline_metrics.append(selector)

    queries = []
    if headline_metrics:
        queries.append(
            AggregationQuery(
                group_by="county",
                metrics=headline_metrics,
                sort_by="population",
                limit=25,
            )
        )
    if distribution_metrics:
        queries.append(
            AggregationQuery(
                group_by="zip",
                metrics=distribution_metrics[:4],
                sort_by="population",
                limit=ZIP_ROW_LIMIT,
            )
        )
    return QueryPlan(queries=queries, reasoning="Deterministic fallback plan")
