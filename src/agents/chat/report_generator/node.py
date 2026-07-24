"""Report Generator node: execute the query plan deterministically, then write
the report section by section — an outline call, one structured-output call per
section, and a summary call — and assemble the Report in code.

Sectioned generation keeps every LLM response small enough to never hit the
output-token cap (a single whole-report call used to truncate and fail
validation), and a failed section degrades the report instead of crashing it.

Location preferences are injected here as WHERE-clause filters on every query;
the plan itself carries no location, so scope cannot be widened or dropped.
"""

import asyncio
import json
from datetime import UTC, datetime
from uuid import uuid4

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from src.agents.chat.base import SubAgent
from src.agents.chat.graph_state import GraphState
from src.agents.chat.report_generator import prompts
from src.core.database import AsyncSessionLocal, Report
from src.core.logging import get_logger
from src.core.services.zips import get_aggregation
from src.schemas.aggregation import QueryPlan
from src.schemas.preferences import LocationPreference, Preferences, load_preferences
from src.schemas.report import Report as ReportSchema
from src.schemas.report import ReportOutline, ReportSection, ReportSummary

logger = get_logger(__name__)

NO_DATA_MESSAGE = (
    "I wasn't able to retrieve demographic data for your requested scope, so I "
    "can't generate a reliable report right now. Please try again, or broaden "
    "the location preference."
)

# Generous headroom for the largest single call (a section whose violin/histogram
# visualization carries ~100 ZIP-level data points).
MAX_OUTPUT_TOKENS = 8192


class ReportGenerator(SubAgent):
    """Run planned queries with location WHERE filters; write and persist the report."""

    def __init__(self) -> None:
        super().__init__(max_tokens=MAX_OUTPUT_TOKENS)

    async def __call__(self, state: GraphState, config: RunnableConfig) -> dict:
        preferences = load_preferences(state.get("preferences")) or Preferences()
        location = preferences.location or LocationPreference()
        plan = QueryPlan.model_validate(state.get("query_plan") or {})

        results, failures = await execute_plan(plan, location)

        if not results:
            return {"messages": [AIMessage(content=NO_DATA_MESSAGE)], "report": None}

        report = await self.write_report(
            preferences=preferences,
            location=location,
            results=results,
            failures=failures,
            profile_id=state.get("profile_id"),
        )
        if report is None:
            return {"messages": [AIMessage(content=NO_DATA_MESSAGE)], "report": None}

        # Persist to DB
        thread_id = config["configurable"]["thread_id"]
        async with AsyncSessionLocal() as session:
            db_report = Report(
                id=report.report_id,
                client_profile_id=report.client_profile_id,
                conversation_id=thread_id,
                title=report.title,
                subtitle=report.subtitle,
                geography_type=report.geography_type,
                geography_value=report.geography_value,
                summary=report.summary.model_dump(),
                sections=[s.model_dump() for s in report.sections],
            )
            session.add(db_report)
            await session.commit()

        return {"report": report}

    async def write_report(
        self,
        preferences: Preferences,
        location: LocationPreference,
        results: list[dict],
        failures: list[str],
        profile_id: str | None,
    ) -> ReportSchema | None:
        """Outline the report, write each section and the summary concurrently,
        and assemble the Report in code. Returns None if the outline or summary
        fails, or no section survives."""
        context = {
            "client_name": preferences.name,
            "business_type": preferences.business_type,
            "service_description": preferences.service_description,
            "target_customer_description": preferences.target_customer_description,
            "location_description": location.describe(),
            "query_results": format_results(results, failures),
        }

        try:
            outline = await self._generate(ReportOutline, prompts.OUTLINE_PROMPT.format(**context))
        except Exception:
            logger.exception("Report outline generation failed")
            return None

        section_calls = [
            self._generate(
                ReportSection,
                prompts.WRITE_SECTION_PROMPT.format(
                    report_title=outline.title,
                    section_title=item.title,
                    section_focus=item.focus,
                    **context,
                ),
                method="function_calling",
            )
            for item in outline.sections
        ]
        summary_call = self._generate(
            ReportSummary,
            prompts.WRITE_SUMMARY_PROMPT.format(
                report_title=outline.title,
                section_titles="; ".join(item.title for item in outline.sections),
                **context,
            ),
        )
        *section_results, summary = await asyncio.gather(
            *section_calls, summary_call, return_exceptions=True
        )

        if isinstance(summary, BaseException):
            logger.error("Report summary generation failed: %s", summary)
            return None

        sections: list[ReportSection] = []
        for item, result in zip(outline.sections, section_results):
            if isinstance(result, BaseException):
                logger.error("Section %r generation failed: %s", item.title, result)
                continue
            sections.append(result)
        if not sections:
            logger.error("All %d section generations failed", len(outline.sections))
            return None

        # Ids and ranks are assigned here, not by the LLM.
        for rank, section in enumerate(sections, 1):
            section.rank = rank
            section.section_id = f"section-{rank}"
            for i, viz in enumerate(section.visualizations, 1):
                viz.visualization_id = f"{section.section_id}-viz-{i}"

        return ReportSchema(
            report_id=str(uuid4()),
            title=outline.title,
            subtitle=outline.subtitle,
            geography_type=results[0]["group_by"],
            geography_value=location.describe(),
            client_profile_id=profile_id,
            summary=summary,
            sections=sections,
            generated_at=datetime.now(UTC).isoformat(),
        )

    async def _generate[T: BaseModel](
        self, schema: type[T], prompt: str, *, method: str = "json_schema"
    ) -> T:
        """One structured-output call, retried once — a single retry is cheap
        now that each call produces one small piece of the report.

        json_schema (API-side constrained decoding, output can never fail
        validation) is the default; ReportSection must use function_calling
        because its grammar is too complex to compile ("Grammar compilation
        timed out" 400s).
        """
        llm = self.llm.with_structured_output(schema, method=method)
        messages = [{"role": "user", "content": prompt}]
        try:
            return await llm.ainvoke(messages)
        except Exception as exc:
            logger.warning("%s generation failed (%s); retrying once", schema.__name__, exc)
            return await llm.ainvoke(messages)


async def execute_plan(
    plan: QueryPlan, location: LocationPreference
) -> tuple[list[dict], list[str]]:
    """Run every planned query with the location's WHERE filters injected.

    Returns (results, failure_notes); a failed query is noted and skipped.
    """
    filter_kwargs = location.filter_kwargs()
    results: list[dict] = []
    failures: list[str] = []

    async with AsyncSessionLocal() as session:
        for query in plan.queries:
            try:
                response = await get_aggregation(
                    session=session,
                    group_by=query.group_by,
                    metric_selectors=query.metrics,
                    sort_by=query.sort_by,
                    sort_dir=query.sort_dir,
                    limit=query.limit,
                    **filter_kwargs,
                )
                results.append(
                    {
                        "group_by": query.group_by,
                        "metrics": query.metrics,
                        "rows": [row.model_dump() for row in response.rows],
                    }
                )
            except Exception as exc:
                failures.append(f"{query.group_by} query for {query.metrics}: {exc}")

    return results, failures


def format_results(results: list[dict], failures: list[str]) -> str:
    """Render query results as compact JSON blocks for the report prompt."""
    blocks = []
    for i, result in enumerate(results, 1):
        blocks.append(
            f"--- Result {i}: grouped by {result['group_by']}, "
            f"metrics {', '.join(result['metrics'])} ---\n"
            + json.dumps(result["rows"], default=str)
        )
    for note in failures:
        blocks.append(f"--- Failed query (no data): {note} ---")
    return "\n\n".join(blocks)
