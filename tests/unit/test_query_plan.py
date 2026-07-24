"""Tests for the Data Analyst's QueryPlan validation and guardrails."""

from src.agents.chat.data_analyst.node import ZIP_ROW_LIMIT, apply_guardrails, fallback_plan
from src.schemas.aggregation import AggregationQuery, QueryPlan
from src.schemas.preferences import LocationPreference, Preferences


def _prefs(location: LocationPreference | None) -> Preferences:
    return Preferences(demographic_categories=["education", "income"], location=location)


class TestAggregationQueryValidation:
    def test_invalid_metrics_dropped(self):
        query = AggregationQuery(
            group_by="county",
            metrics=[
                "education.bachelors_degree_or_higher",  # invalid (the old failure)
                "education.college_or_above",  # valid
                "not-a-selector",
            ],
        )
        assert query.metrics == ["education.college_or_above"]

    def test_no_location_fields_on_query(self):
        # Location must be structurally impossible in a planned query.
        assert not ({"region", "state", "states", "cbsa", "city"} & set(AggregationQuery.model_fields))


class TestGuardrails:
    def test_state_group_by_rewritten_under_location_scope(self):
        """Regression: the east-coast report grouped by state and leaked CA/TX."""
        plan = QueryPlan(
            queries=[AggregationQuery(group_by="state", metrics=["income.median_household_income"])]
        )
        location = LocationPreference(region="east_coast")

        result = apply_guardrails(plan, _prefs(location))
        assert result.queries[0].group_by == "county"

    def test_state_group_by_allowed_nationwide(self):
        plan = QueryPlan(
            queries=[AggregationQuery(group_by="state", metrics=["income.median_household_income"])]
        )
        result = apply_guardrails(plan, _prefs(None))
        assert result.queries[0].group_by == "state"

    def test_empty_metric_queries_dropped(self):
        plan = QueryPlan(
            queries=[
                AggregationQuery(group_by="county", metrics=["bogus.metric"]),
                AggregationQuery(group_by="county", metrics=["income.median_household_income"]),
            ]
        )
        result = apply_guardrails(plan, _prefs(None))
        assert len(result.queries) == 1

    def test_zip_limit_capped(self):
        plan = QueryPlan(
            queries=[AggregationQuery(group_by="zip", metrics=["income.distribution"], limit=1000)]
        )
        result = apply_guardrails(plan, _prefs(None))
        assert result.queries[0].limit == ZIP_ROW_LIMIT

    def test_degenerate_plan_falls_back(self):
        result = apply_guardrails(QueryPlan(queries=[]), _prefs(LocationPreference(states=["Georgia"])))
        assert result.queries, "fallback plan must not be empty"


class TestFallbackPlan:
    def test_covers_preferred_categories_and_core(self):
        plan = fallback_plan(_prefs(None))
        all_metrics = [m for q in plan.queries for m in q.metrics]
        assert any(m.startswith("education.") for m in all_metrics)
        assert any(m.startswith("income.") for m in all_metrics)

    def test_has_county_ranking_and_zip_distribution(self):
        plan = fallback_plan(_prefs(None))
        group_bys = {q.group_by for q in plan.queries}
        assert group_bys == {"county", "zip"}
        zip_query = next(q for q in plan.queries if q.group_by == "zip")
        assert zip_query.limit <= ZIP_ROW_LIMIT
        assert all(".distribution" in m for m in zip_query.metrics)
