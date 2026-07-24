"""Tests for the Report Generator: deterministic query execution and the
sectioned (outline -> per-section -> summary) report assembly."""

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.chat.report_generator.node import ReportGenerator, execute_plan, format_results
from src.core.urbanicity import URBAN_MIN_DENSITY
from src.schemas.aggregation import AggregationQuery, AggregationResponse, QueryPlan
from src.schemas.preferences import LocationPreference, Preferences
from src.schemas.report import (
    ReportOutline,
    ReportSection,
    ReportSummary,
    SectionOutline,
)


def _plan() -> QueryPlan:
    return QueryPlan(
        queries=[AggregationQuery(group_by="county", metrics=["income.median_household_income"])]
    )


@pytest.mark.asyncio
async def test_location_filters_injected_into_every_query():
    """Regression: location must reach the WHERE clause; the LLM can't omit it."""
    location = LocationPreference(region="east_coast", area_type="urban")
    fake_response = AggregationResponse(rows=[], limit=50, offset=0)

    with patch(
        "src.agents.chat.report_generator.node.get_aggregation",
        new=AsyncMock(return_value=fake_response),
    ) as mock_agg, patch("src.agents.chat.report_generator.node.AsyncSessionLocal"):
        await execute_plan(_plan(), location)

    kwargs = mock_agg.call_args.kwargs
    assert kwargs["region"] == "east_coast"
    assert kwargs["min_density"] == URBAN_MIN_DENSITY
    assert kwargs["group_by"] == "county"


@pytest.mark.asyncio
async def test_failed_query_is_noted_and_skipped():
    location = LocationPreference(states=["Georgia"])
    plan = QueryPlan(
        queries=[
            AggregationQuery(group_by="county", metrics=["income.median_household_income"]),
            AggregationQuery(group_by="zip", metrics=["age.distribution"]),
        ]
    )
    ok = AggregationResponse(rows=[], limit=50, offset=0)

    with patch(
        "src.agents.chat.report_generator.node.get_aggregation",
        new=AsyncMock(side_effect=[RuntimeError("boom"), ok]),
    ), patch("src.agents.chat.report_generator.node.AsyncSessionLocal"):
        results, failures = await execute_plan(plan, location)

    assert len(results) == 1
    assert len(failures) == 1
    assert "boom" in failures[0]


def test_format_results_includes_failures():
    text = format_results(
        [{"group_by": "county", "metrics": ["income.median_household_income"], "rows": []}],
        ["zip query for ['age.distribution']: boom"],
    )
    assert "grouped by county" in text
    assert "Failed query" in text


# =============================================================================
# Sectioned report assembly (write_report)
# =============================================================================

_OUTLINE = ReportOutline(
    title="Income Hotspots",
    subtitle="Urban East Coast",
    sections=[
        SectionOutline(title="Income", focus="County income ranking from result 1."),
        SectionOutline(title="Age", focus="ZIP age distribution from result 2."),
    ],
)
_SUMMARY = ReportSummary(total_population=100_000, zip_count=42)
_RESULTS = [{"group_by": "county", "metrics": ["income.median_household_income"], "rows": []}]


def _section(title: str) -> ReportSection:
    return ReportSection(section_id="llm-invented", title=title, rank=99)


def _generator(outline=_OUTLINE, sections=None, summary=_SUMMARY) -> ReportGenerator:
    """ReportGenerator with _generate stubbed per schema; no real LLM is built.

    `sections` entries may be exceptions, which the stub raises — simulating a
    failed or invalid structured-output call for that one section.
    """
    generator = ReportGenerator.__new__(ReportGenerator)
    section_queue = list(sections if sections is not None else [_section("Income"), _section("Age")])

    async def fake_generate(schema, prompt, *, method="json_schema"):
        if schema is ReportOutline:
            return outline
        if schema is ReportSummary:
            if isinstance(summary, Exception):
                raise summary
            return summary
        result = section_queue.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    generator._generate = fake_generate
    return generator


async def _write_report(generator: ReportGenerator):
    return await generator.write_report(
        preferences=Preferences(),
        location=LocationPreference(states=["Georgia"]),
        results=_RESULTS,
        failures=[],
        profile_id="profile-1",
    )


@pytest.mark.asyncio
async def test_write_report_assembles_sections_in_outline_order():
    report = await _write_report(_generator())

    assert report is not None
    assert report.title == "Income Hotspots"
    assert report.geography_type == "county"
    assert report.client_profile_id == "profile-1"
    assert report.summary.total_population == 100_000
    assert [s.title for s in report.sections] == ["Income", "Age"]
    # Ids and ranks are assigned in code, not taken from the LLM output.
    assert [(s.section_id, s.rank) for s in report.sections] == [("section-1", 1), ("section-2", 2)]


@pytest.mark.asyncio
async def test_failed_section_is_dropped_not_fatal():
    """Regression: a validation error used to kill the whole report; now it
    costs only the affected section."""
    generator = _generator(sections=[ValueError("truncated output"), _section("Age")])

    report = await _write_report(generator)

    assert report is not None
    assert [s.title for s in report.sections] == ["Age"]
    assert report.sections[0].rank == 1


@pytest.mark.asyncio
async def test_summary_failure_returns_none():
    report = await _write_report(_generator(summary=ValueError("boom")))
    assert report is None


@pytest.mark.asyncio
async def test_all_sections_failing_returns_none():
    generator = _generator(sections=[ValueError("a"), ValueError("b")])
    report = await _write_report(generator)
    assert report is None
