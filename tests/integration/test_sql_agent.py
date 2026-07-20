"""Tests for SQL Agent report generation (see sql_agent_pseudocode.md).

Covers each step of the spec:
1. Query extraction per demographic category (LLM + query tools)
2. Importance ranking via importance_weight
3. Visualization selection and conversion to response models
4. Section grouping with descriptions
5. Section importance = average of visualization weights, top-N kept
6. Router configuration and orchestrator wiring (Report + report_output.json)

Unit tests (TestSectionAssembly, TestVisualizationBuilding, TestRouterConfiguration)
run without a database or LLM. Integration tests require:
1. A running PostgreSQL database with uszips data
2. OpenAI API key for LLM calls

Run with: just test-sql-agent
"""

import logging

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.agents.orchestrator.demographics import DEMOGRAPHICS
from src.agents.sql_analyst.agent import (
    SQLAgent,
    build_report_sections,
    build_visualization,
    generate_report,
    resolve_metric_name,
    select_categories,
)
from src.agents.sql_analyst.models import (
    CategoryResult,
    QueryExtraction,
    SectionGrouping,
    VisualizationChoice,
)
from src.agents.sql_analyst.tools import (
    AggregatedDemographics,
    query_aggregated_demographics,
)
from src.agents.sql_analyst.utils import (
    GeographyLevel,
    build_demographic_where,
    resolve_demographic_column,
)
from src.core.config import get_settings
from src.core.state import ClientProfileRef, DemographicTargetRef
from src.schemas.report import Report


# ---------------------------------------------------------------------------
# Sample Business Profiles (fictitious, per spec Validation section)
# ---------------------------------------------------------------------------


def make_spanish_tutor_profile() -> ClientProfileRef:
    """Spanish Tutor / Cultural Center profile.

    Business context: A Spanish tutor expanding into a cultural immersion center
    where Spanish and English speakers can share cultures and learn a second language.

    Target demographics:
    - Hispanic population (potential Spanish-speaking community)
    - Limited English speakers (market for English instruction)
    - College educated (learning orientation)
    - Income >= $50k (can afford classes)
    """
    return ClientProfileRef(
        profile_id="test_spanish_tutor_001",
        name="Casa de Cultura",
        business_type="Education / Cultural Center",
        service_description="Spanish language tutoring and cultural immersion programs "
        "where Spanish and English speakers learn each other's language and culture",
        target_demographics=[
            DemographicTargetRef(
                demographic_key="hispanic",
                constraint_type="percentage",
                target_percentage=15.0,
                percentage_operator="gte",
                importance_weight=0.9,
            ),
            DemographicTargetRef(
                demographic_key="limited_english",
                constraint_type="percentage",
                target_percentage=5.0,
                percentage_operator="gte",
                importance_weight=0.8,
            ),
            DemographicTargetRef(
                demographic_key="education_college_or_above",
                constraint_type="percentage",
                target_percentage=30.0,
                percentage_operator="gte",
                importance_weight=0.6,
            ),
            DemographicTargetRef(
                demographic_key="income_household_median",
                constraint_type="threshold_min",
                min_value=50000.0,
                importance_weight=0.5,
            ),
        ],
    )


def make_luxury_fitness_profile() -> ClientProfileRef:
    """Luxury Fitness Studio profile.

    Business context: A premium fitness studio targeting affluent professionals
    who want high-end workout experiences.

    Target demographics:
    - Six-figure household income
    - Age 30-55 (prime earning years)
    - College educated
    """
    return ClientProfileRef(
        profile_id="test_luxury_fitness_001",
        name="Elevate Fitness Studio",
        business_type="Fitness / Wellness",
        service_description="Premium boutique fitness studio offering personalized "
        "training, recovery services, and luxury amenities for discerning clients",
        target_demographics=[
            DemographicTargetRef(
                demographic_key="income_household_six_figure",
                constraint_type="percentage",
                target_percentage=20.0,
                percentage_operator="gte",
                importance_weight=0.95,
            ),
            DemographicTargetRef(
                demographic_key="income_household_median",
                constraint_type="threshold_min",
                min_value=100000.0,
                importance_weight=0.9,
            ),
            DemographicTargetRef(
                demographic_key="education_college_or_above",
                constraint_type="percentage",
                target_percentage=50.0,
                percentage_operator="gte",
                importance_weight=0.7,
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Test data builders (no DB or LLM required)
# ---------------------------------------------------------------------------


def make_category_result(
    category: str,
    metric_name: str,
    importance_weight: float,
    chart_type: str = "bar",
) -> CategoryResult:
    """Build a CategoryResult as the LLM extraction/ranking steps would."""
    return CategoryResult(
        category=category,
        extraction=QueryExtraction(
            category=category,
            metric_name=metric_name,
            reasoning="test",
        ),
        visualization_choice=VisualizationChoice(
            chart_type=chart_type,
            title=f"{category} - {metric_name}",
            importance_weight=importance_weight,
            reasoning="test",
        ),
        row_count=2,
        data_summary="test summary",
    )


def make_state_rows() -> list[AggregatedDemographics]:
    """Fabricate state-level query rows with race columns."""
    return [
        AggregatedDemographics(
            state_name="Texas",
            population=1000.0,
            hispanic=40.0,
            race_white=50.0,
            race_black=12.0,
        ),
        AggregatedDemographics(
            state_name="California",
            population=3000.0,
            hispanic=39.0,
            race_white=40.0,
            race_black=6.0,
        ),
    ]


# ---------------------------------------------------------------------------
# Spec: 11 demographic categories
# ---------------------------------------------------------------------------


def test_demographics_has_11_categories():
    """The agent must iterate through all 11 demographic categories."""
    assert len(DEMOGRAPHICS.get_all_categories()) == 11


class TestMetricNameResolution:
    """LLM metric names are resolved so query tool calls succeed."""

    def test_exact_metric_name_passes_through(self):
        assert resolve_metric_name("race", "hispanic") == "hispanic"

    def test_column_name_resolves_to_metric_name(self):
        # LLMs sometimes return the SQL column instead of the metric key
        assert resolve_metric_name("health", "health_uninsured") == "uninsured"
        assert (
            resolve_metric_name("income", "income_household_six_figure")
            == "six_figure_households"
        )

    def test_distribution_column_resolves_to_distribution_metric(self):
        assert resolve_metric_name("race", "race_black") == "distribution"

    def test_unknown_name_returns_none(self):
        assert resolve_metric_name("race", "not_a_metric") is None


class TestDemographicTargetResolution:
    """Orchestrator-persisted demographic_keys (metric names) must build valid SQL.

    Regression: the orchestrator validates and stores DEMOGRAPHICS metric names
    (e.g. 'median_household_income'), but the uszips column is
    'income_household_median'. Interpolating the key directly produced
    UndefinedColumn errors that failed ALL category queries -> empty report.
    """

    def test_metric_name_resolves_to_sql_column(self):
        assert resolve_demographic_column("median_household_income") == "income_household_median"
        assert resolve_demographic_column("college_or_above") == "education_college_or_above"
        assert resolve_demographic_column("six_figure_households") == "income_household_six_figure"
        assert resolve_demographic_column("median_age") == "age_median"

    def test_column_name_passes_through(self):
        assert resolve_demographic_column("income_household_median") == "income_household_median"
        assert resolve_demographic_column("hispanic") == "hispanic"

    def test_unknown_key_returns_none(self):
        assert resolve_demographic_column("not_a_real_key") is None

    def test_every_valid_orchestrator_key_resolves(self):
        """Every key the orchestrator can persist must resolve to a column."""
        from src.agents.orchestrator.agent import Orchestrator

        orchestrator = Orchestrator.__new__(Orchestrator)  # skip LLM init
        for key in orchestrator._get_valid_demographic_keys():
            assert resolve_demographic_column(key) is not None, (
                f"Orchestrator key '{key}' does not resolve to a SQL column"
            )

    def test_where_clause_uses_columns_and_skips_unknown_keys(self):
        targets = [
            DemographicTargetRef(
                demographic_key="median_household_income",
                constraint_type="threshold_min",
                min_value=50000.0,
            ),
            DemographicTargetRef(
                demographic_key="not_a_real_key",
                constraint_type="threshold_min",
                min_value=1.0,
            ),
        ]
        where = build_demographic_where(targets)
        assert "income_household_median >= 50000.0" in where
        assert "not_a_real_key" not in where


class TestCategorySelection:
    """Categories are derived from target_demographics, not hardcoded to all 11."""

    def test_metric_key_resolves_to_category(self):
        assert DEMOGRAPHICS.category_for_metric("hispanic") == "race"
        assert DEMOGRAPHICS.category_for_metric("median_household_income") == "income"

    def test_column_name_resolves_to_category(self):
        # Persisted targets sometimes store SQL column names
        assert DEMOGRAPHICS.category_for_metric("income_household_median") == "income"
        assert DEMOGRAPHICS.category_for_metric("education_college_or_above") == "education"

    def test_distribution_column_resolves_to_category(self):
        assert DEMOGRAPHICS.category_for_metric("race_black") == "race"

    def test_unknown_name_returns_none(self):
        assert DEMOGRAPHICS.category_for_metric("not_a_metric") is None

    def test_no_targets_falls_back_to_all_categories(self):
        assert select_categories(None) == DEMOGRAPHICS.get_all_categories()
        assert select_categories([]) == DEMOGRAPHICS.get_all_categories()

    def test_unmappable_targets_fall_back_to_all_categories(self):
        targets = [
            DemographicTargetRef(
                demographic_key="not_a_real_key",
                constraint_type="threshold_min",
                min_value=1.0,
            )
        ]
        assert select_categories(targets) == DEMOGRAPHICS.get_all_categories()

    def test_spanish_tutor_targets_select_relevant_categories(self):
        profile = make_spanish_tutor_profile()
        # mapped {race, language, education, income} | core {income, age, education}
        assert select_categories(profile.target_demographics) == [
            "race",
            "age",
            "income",
            "education",
            "language",
        ]

    def test_luxury_fitness_targets_pad_to_minimum(self):
        profile = make_luxury_fitness_profile()
        # mapped {income, education} | core {income, age, education} = 3,
        # padded with housing + employment to reach the 5-category minimum
        assert select_categories(profile.target_demographics) == [
            "age",
            "employment",
            "income",
            "education",
            "housing",
        ]


# ---------------------------------------------------------------------------
# Spec step 3: Visualization conversion (deterministic, no LLM)
# ---------------------------------------------------------------------------


class TestVisualizationBuilding:
    """build_visualization converts query rows into Visualization models."""

    def test_percentage_metric_builds_bar_chart(self):
        cat_result = make_category_result("race", "hispanic", 80.0, chart_type="bar")
        viz = build_visualization(cat_result, make_state_rows())

        assert viz.config.chart_type == "bar"
        assert viz.title == "race - hispanic"
        assert viz.categorical_data is not None
        labels = [dp.label for dp in viz.categorical_data]
        assert "Texas" in labels and "California" in labels
        tx = next(dp for dp in viz.categorical_data if dp.label == "Texas")
        assert tx.value == 40.0

    def test_distribution_metric_is_population_weighted(self):
        cat_result = make_category_result("race", "distribution", 70.0, chart_type="pie")
        viz = build_visualization(cat_result, make_state_rows())

        assert viz.config.chart_type == "pie"
        assert viz.categorical_data is not None
        white = next(dp for dp in viz.categorical_data if dp.label == "White")
        # Population-weighted: (50*1000 + 40*3000) / 4000 = 42.5
        assert white.value == pytest.approx(42.5)

    def test_unsupported_chart_type_falls_back_to_bar(self):
        cat_result = make_category_result("race", "hispanic", 60.0, chart_type="violin")
        viz = build_visualization(cat_result, make_state_rows())

        assert viz.config.chart_type == "bar"
        assert viz.categorical_data, "Fallback bar chart must still carry data"


# ---------------------------------------------------------------------------
# Spec steps 4-5: Section grouping, averaged importance, top-N (no LLM)
# ---------------------------------------------------------------------------


class TestSectionAssembly:
    """build_report_sections averages visualization weights and keeps top N."""

    def _results_and_data(self):
        category_results = [
            make_category_result("race", "hispanic", 90.0),
            make_category_result("language", "limited_english", 70.0),
            make_category_result("income", "median_household_income", 50.0),
            make_category_result("transportation", "commute_time", 10.0),
        ]
        all_results = {r.category: make_state_rows() for r in category_results}
        return category_results, all_results

    def test_section_importance_is_average_of_visualization_weights(self):
        category_results, all_results = self._results_and_data()
        groupings = [
            SectionGrouping(
                section_title="Market Demographics",
                section_description="Race and language define the customer base",
                category_names=["race", "language"],
            ),
        ]

        sections = build_report_sections(groupings, category_results, all_results, 5)

        assert len(sections) == 1
        # Average of race (90) and language (70) visualization weights
        assert sections[0].importance_weight == pytest.approx(80.0)
        assert len(sections[0].visualizations) == 2

    def test_top_n_sections_kept_sorted_by_importance(self):
        category_results, all_results = self._results_and_data()
        # LLM returned groupings in the "wrong" order - least important first
        groupings = [
            SectionGrouping(
                section_title="Commute Patterns",
                section_description="How people get around",
                category_names=["transportation"],  # weight 10
            ),
            SectionGrouping(
                section_title="Economic Profile",
                section_description="Spending power",
                category_names=["income"],  # weight 50
            ),
            SectionGrouping(
                section_title="Market Demographics",
                section_description="Core customer base",
                category_names=["race", "language"],  # avg weight 80
            ),
        ]

        sections = build_report_sections(groupings, category_results, all_results, 2)

        # Only top 2 by averaged importance survive, most important first
        assert [s.title for s in sections] == ["Market Demographics", "Economic Profile"]
        assert [s.rank for s in sections] == [1, 2]
        weights = [s.importance_weight for s in sections]
        assert weights == sorted(weights, reverse=True)

    def test_sections_carry_descriptions(self):
        category_results, all_results = self._results_and_data()
        groupings = [
            SectionGrouping(
                section_title="Market Demographics",
                section_description="Why these belong together",
                category_names=["race"],
            ),
        ]

        sections = build_report_sections(groupings, category_results, all_results, 5)
        assert sections[0].description == "Why these belong together"

    def test_grouping_with_no_matching_categories_is_dropped(self):
        category_results, all_results = self._results_and_data()
        groupings = [
            SectionGrouping(
                section_title="Empty Section",
                section_description="References a category with no results",
                category_names=["health"],  # no query results for health
            ),
        ]

        sections = build_report_sections(groupings, category_results, all_results, 5)
        assert sections == []

    def test_empty_groupings_produce_empty_sections(self):
        category_results, all_results = self._results_and_data()
        assert build_report_sections([], category_results, all_results, 5) == []


# ---------------------------------------------------------------------------
# Spec: "Finally, configure the router" (no LLM)
# ---------------------------------------------------------------------------


class TestRouterConfiguration:
    """Orchestrator initial_router routes to query_node once profile is ready."""

    def _make_state(self, preferences, client_profile, asked_for_more=False):
        return {
            "messages": [],
            "preferences": preferences,
            "client_profile": client_profile,
            "asked_for_more": asked_for_more,
            "report": None,
        }

    def _complete_preferences(self):
        from src.agents.orchestrator.agent import Preferences

        return Preferences(
            name="Casa de Cultura",
            business_category="Education / Cultural Center",
            services_products="Spanish tutoring and cultural immersion",
            price_point="mid-market",
            target_customer="Hispanic families and English speakers learning Spanish",
            location_preferences="Texas and California",
        )

    def test_routes_to_discovery_when_preferences_incomplete(self):
        from src.agents.orchestrator.agent import Orchestrator, Preferences

        state = self._make_state(Preferences(), None)
        assert Orchestrator().initial_router(state) == "discovery"

    def test_routes_to_profile_builder_when_no_profile(self):
        from src.agents.orchestrator.agent import Orchestrator

        state = self._make_state(self._complete_preferences(), None)
        assert Orchestrator().initial_router(state) == "profile_builder"

    def test_routes_to_demographics_when_few_targets(self):
        from src.agents.orchestrator.agent import Orchestrator

        profile = make_spanish_tutor_profile()
        profile.target_demographics = profile.target_demographics[:2]
        state = self._make_state(self._complete_preferences(), profile)
        assert Orchestrator().initial_router(state) == "get_target_demographics"

    def test_routes_to_query_node_when_profile_complete(self):
        from src.agents.orchestrator.agent import Orchestrator

        state = self._make_state(self._complete_preferences(), make_spanish_tutor_profile())
        assert Orchestrator().initial_router(state) == "query_node"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncSession:
    """Get fresh async database session for each test."""
    settings = get_settings()
    engine = create_async_engine(settings.async_database_url, echo=False)
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session
    await engine.dispose()


# ---------------------------------------------------------------------------
# Spec coding standard: query tool observability (DB, no LLM)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_query_tool_logs_result_counts(db_session, caplog):
    """All query tool calls must log their result counts for observability."""
    with caplog.at_level(logging.INFO, logger="src.agents.sql_analyst.tools"):
        results = await query_aggregated_demographics(
            session=db_session,
            category="race",
            metric_name="hispanic",
            geography_level=GeographyLevel.STATE,
        )

    assert len(results) > 0
    assert any(
        "returned" in record.message for record in caplog.records
    ), "query tool should log row counts"


@pytest.mark.asyncio
async def test_query_with_orchestrator_style_target_keys(db_session):
    """Regression: targets stored with metric names (as the orchestrator does)
    must not produce UndefinedColumn errors and must return rows."""
    targets = [
        DemographicTargetRef(
            demographic_key="median_household_income",  # column: income_household_median
            constraint_type="threshold_min",
            min_value=50000.0,
        ),
        DemographicTargetRef(
            demographic_key="college_or_above",  # column: education_college_or_above
            constraint_type="percentage",
            target_percentage=25.0,
            percentage_operator="gte",
        ),
    ]

    results = await query_aggregated_demographics(
        session=db_session,
        category="race",
        metric_name="hispanic",
        geography_level=GeographyLevel.STATE,
        demographic_targets=targets,
    )

    assert len(results) > 0, "metric-name target keys should filter, not fail"


# ---------------------------------------------------------------------------
# Spec steps 1-3: Single category extraction + ranking (DB + LLM)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_process_category_extracts_valid_metric_and_ranks(db_session):
    """LLM extracts a real metric for the category, and ranks importance 0-100."""
    profile = make_spanish_tutor_profile()
    agent = SQLAgent(db_session)

    outcome = await agent.process_category(
        category="race",
        profile=profile,
        geography_level=GeographyLevel.STATE,
        state_names=None,
        region_name="south",
        cbsa_names=None,
    )

    assert outcome is not None, "race category should return results for the South"
    result, rows = outcome

    assert result.category == "race"
    # Extracted metric must exist in the category (query tools depend on this)
    assert result.extraction.metric_name in DEMOGRAPHICS.get_category("race").metrics
    assert 0 <= result.visualization_choice.importance_weight <= 100
    assert result.visualization_choice.chart_type in (
        "bar",
        "pie",
        "violin",
        "histogram",
        "bubble",
    )
    assert result.row_count == len(rows) > 0


# ---------------------------------------------------------------------------
# Full pipeline happy path (DB + LLM)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "profile_factory,geography,expected_min_pop",
    [
        (make_spanish_tutor_profile, {"region_name": "south"}, 50_000_000),
        (make_luxury_fitness_profile, {"state_names": ["California", "Texas"]}, 50_000_000),
    ],
    ids=["spanish_tutor_south_region", "luxury_fitness_ca_tx"],
)
@pytest.mark.asyncio
async def test_sql_agent_happy_path(db_session, profile_factory, geography, expected_min_pop):
    """End-to-end test: profile -> report with sections and visualizations."""
    profile = profile_factory()

    report = await generate_report(
        session=db_session,
        client_profile=profile,
        geography_level=GeographyLevel.STATE,
        **geography,
    )

    # Core assertions
    assert report is not None
    assert report.report_id is not None
    assert profile.name in report.title
    assert report.summary.total_population >= expected_min_pop
    assert report.summary.narrative is not None
    assert 1 <= len(report.sections) <= 5

    # Report must round-trip through JSON (D3 frontend consumes JSON)
    assert Report.model_validate_json(report.model_dump_json()) is not None

    # Spec steps 4-5: sections are described, ranked, and sorted by importance
    weights = [s.importance_weight for s in report.sections]
    assert weights == sorted(weights, reverse=True), "sections must be sorted by importance"
    assert [s.rank for s in report.sections] == list(range(1, len(report.sections) + 1))
    for section in report.sections:
        assert section.description, f"Section '{section.title}' missing description"
        assert 0 <= section.importance_weight <= 100

    # Bubble chart may be None if LLM returns invalid metric names
    # This is acceptable - the chart is optional enhancement
    if report.summary.opportunity_bubble_chart is not None:
        assert len(report.summary.opportunity_bubble_chart.bubble_data) > 0

    # Verify each section has visualizations with data
    for section in report.sections:
        assert len(section.visualizations) > 0
        for viz in section.visualizations:
            has_data = (
                (viz.categorical_data and len(viz.categorical_data) > 0)
                or (viz.distribution_data and len(viz.distribution_data) > 0)
                or (viz.bubble_data and len(viz.bubble_data) > 0)
            )
            assert has_data, f"Visualization '{viz.title}' has no data"

    # Print summary for visibility
    print(f"\n{'='*60}")
    print(f"Report: {report.title}")
    print(f"Geography: {report.geography_value}")
    print(f"Total Population: {report.summary.total_population:,}")
    print(f"Areas: {report.summary.zip_count}")
    print(f"Sections: {len(report.sections)}")
    for section in report.sections:
        print(
            f"  - {section.title} (weight={section.importance_weight:.0f}): "
            f"{len(section.visualizations)} visualizations"
        )
    print(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# Orchestrator wiring: query_node produces Report + report_output.json
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orchestrator_query_node_produces_report_and_json(tmp_path, monkeypatch):
    """The agent wired into the orchestrator emits the Report and its JSON file."""
    import src.agents.orchestrator.agent as orchestrator_module
    from src.agents.orchestrator.agent import Orchestrator, Preferences

    output_path = tmp_path / "report_output.json"
    monkeypatch.setattr(orchestrator_module, "REPORT_OUTPUT_PATH", output_path)

    state = {
        "messages": [],
        "preferences": Preferences(
            name="Casa de Cultura",
            business_category="Education / Cultural Center",
            services_products="Spanish tutoring and cultural immersion",
            price_point="mid-market",
            target_customer="Hispanic families and English learners",
            location_preferences="Texas and California",
        ),
        "client_profile": make_spanish_tutor_profile(),
        "asked_for_more": False,
        "report": None,
    }

    result = await Orchestrator().query_node(state)

    # Report pydantic object in state update
    report = result.get("report")
    assert isinstance(report, Report)
    assert len(report.sections) >= 1
    assert report.summary.total_population > 0

    # JSON file written and loadable back into the Report model
    assert output_path.exists(), "query_node must write report_output.json"
    loaded = Report.model_validate_json(output_path.read_text())
    assert loaded.report_id == report.report_id
    assert len(loaded.sections) == len(report.sections)
