"""Evaluation harness for the Prospector agentic system.

Runs each business brief in evals/dataset/ end-to-end through
Orchestrator.chat(), measuring per report:
- Latency (total wall-clock + per-stage from timing logs)
- Token usage (all nested LLM calls via usage-metadata callback)
- Tool selection accuracy (parsed from sql_analyst log lines)
- Report quality (LLM-as-judge scores + human_report_quality field
  left null for manual review)

Results are written incrementally after every business so a mid-run
failure loses nothing; already-evaluated businesses are skipped on rerun.

Usage:
    just eval                  # full dataset, resumes automatically
    just eval-one 01_cultura_connect
    just eval-force            # redo everything
"""

import argparse
import asyncio
import csv
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, get_args

from langchain_core.callbacks import get_usage_metadata_callback

from src.agents.orchestrator.agent import Orchestrator
from src.agents.orchestrator.demographics import CategoryName
from src.core.database import close_checkpointer, init_checkpointer
from src.core.logging import configure_logging, get_logger
from src.schemas.report import Report

from evals.judge import judge_report

logger = get_logger(__name__)

DATASET_DIR = Path("evals/dataset")
RESULTS_DIR = Path("evals/results")
MAX_FOLLOWUP_RETRIES = 1
CATEGORY_NAMES: frozenset[str] = frozenset(get_args(CategoryName))

# Loggers whose records carry the tool-selection and stage-latency signals
CAPTURED_LOGGERS = ("timing", "src.agents.sql_analyst.agent")

STAGE_DONE_RE = re.compile(r"[✓✗] (.+?) \((\d+(?:\.\d+)?)s\)")
EXTRACT_START_RE = re.compile(r"▶ llm:(\w+)\.extract")
RESCUED_RE = re.compile(r"process_category: (\w+) resolved metric")
UNRESOLVABLE_RE = re.compile(r"process_category: (\w+) unresolvable metric")
QUERY_FAILED_RE = re.compile(r"process_category: (\w+) query failed")
ZERO_ROWS_RE = re.compile(r"process_category: (\w+) returned 0 rows")


class LogCapture(logging.Handler):
    """Root-attached handler that records log lines from selected loggers."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[tuple[str, str]] = []  # (logger_name, message)

    def emit(self, record: logging.LogRecord) -> None:
        if record.name in CAPTURED_LOGGERS:
            self.records.append((record.name, record.getMessage()))


def parse_tool_selection(records: list[tuple[str, str]]) -> dict[str, Any]:
    """Compute tool-selection accuracy from captured log lines.

    'Attempted' categories come from timing lines (▶ llm:{category}.extract);
    rescues/failures come from sql_analyst warnings. Success is computed by
    subtraction because the happy-path rows-returned line is a print(),
    not a log record.
    """
    attempted: set[str] = set()
    rescued: set[str] = set()
    unresolvable: set[str] = set()
    query_failed: set[str] = set()
    zero_rows: set[str] = set()

    for name, msg in records:
        if name == "timing":
            if (m := EXTRACT_START_RE.search(msg)) and m.group(1) in CATEGORY_NAMES:
                attempted.add(m.group(1))
        else:
            if m := RESCUED_RE.search(msg):
                rescued.add(m.group(1))
            elif m := UNRESOLVABLE_RE.search(msg):
                unresolvable.add(m.group(1))
            elif m := QUERY_FAILED_RE.search(msg):
                query_failed.add(m.group(1))
            elif m := ZERO_ROWS_RE.search(msg):
                zero_rows.add(m.group(1))

    n = len(attempted)
    first_try_valid = n - len(rescued) - len(unresolvable)
    query_success = n - len(unresolvable) - len(query_failed) - len(zero_rows)

    return {
        "categories_attempted": n,
        "metric_valid_first_try": first_try_valid,
        "metric_rescued": len(rescued),
        "metric_unresolvable": len(unresolvable),
        "query_failures": len(query_failed),
        "zero_row_queries": len(zero_rows),
        "first_try_valid_rate": round(first_try_valid / n, 3) if n else None,
        "query_success_rate": round(query_success / n, 3) if n else None,
    }


def parse_stage_latencies(records: list[tuple[str, str]]) -> dict[str, float]:
    """Per-stage durations from '✓ {step} (N.Ns)' timing lines."""
    stages: dict[str, float] = {}
    for name, msg in records:
        if name == "timing" and (m := STAGE_DONE_RE.search(msg)):
            stages[m.group(1)] = float(m.group(2))
    return stages


def summarize_tokens(usage_metadata: dict[str, Any]) -> dict[str, Any]:
    """Aggregate the callback's per-model usage into flat totals."""
    totals = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    by_model: dict[str, Any] = {}
    for model, usage in usage_metadata.items():
        by_model[model] = {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        }
        for key in totals:
            totals[key] += by_model[model][key]
    return {**totals, "by_model": by_model}


def last_ai_message(state: dict[str, Any]) -> str | None:
    """Content of the most recent AI message, if any."""
    for message in reversed(state.get("messages") or []):
        if getattr(message, "type", None) == "ai":
            return str(message.content)
    return None


def coerce_report(raw: Any) -> Report | None:
    """State report may come back as a Report or a checkpointer-serialized dict."""
    if raw is None or isinstance(raw, Report):
        return raw
    return Report.model_validate(raw)


async def run_one(orchestrator: Orchestrator, business_id: str, brief: str) -> dict[str, Any]:
    """Run one business through the full agentic path and collect metrics."""
    capture = LogCapture()
    logging.getLogger().addHandler(capture)
    thread_id: str | None = None
    report: Report | None = None
    follow_up: str | None = None

    t0 = time.perf_counter()
    try:
        with get_usage_metadata_callback() as cb:
            result = await orchestrator.chat(brief)
            thread_id = result["thread_id"]
            state = result["state"]
            report = coerce_report(state.get("report"))

            # The agent may ask a clarifying question instead of producing a
            # report; re-send the brief once on the same thread (checkpointer
            # keeps extracted preferences).
            retries = 0
            while report is None and retries < MAX_FOLLOWUP_RETRIES:
                retries += 1
                follow_up = last_ai_message(state)
                logger.warning(
                    f"run_one: {business_id} got follow-up question, retrying "
                    f"(attempt {retries}): {follow_up!r:.120}"
                )
                result = await orchestrator.chat(brief, thread_id=thread_id)
                state = result["state"]
                report = coerce_report(state.get("report"))

            if report is None:
                follow_up = last_ai_message(state)
    finally:
        latency = time.perf_counter() - t0
        logging.getLogger().removeHandler(capture)

    metrics: dict[str, Any] = {
        "business_id": business_id,
        "status": "complete" if report is not None else "incomplete",
        "thread_id": thread_id,
        "latency": {
            "total_seconds": round(latency, 1),
            "stages": parse_stage_latencies(capture.records),
        },
        "tokens": summarize_tokens(cb.usage_metadata),
        "tool_selection": parse_tool_selection(capture.records),
        "judge": None,
        "human_report_quality": None,
        "follow_up_question": follow_up,
        "error": None,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return {"metrics": metrics, "report": report}


def write_json_atomic(path: Path, payload: str) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(payload)
    os.replace(tmp, path)


def write_business_results(business_id: str, report: Report | None, metrics: dict) -> None:
    out_dir = RESULTS_DIR / business_id
    out_dir.mkdir(parents=True, exist_ok=True)
    if report is not None:
        write_json_atomic(out_dir / "report.json", report.model_dump_json(indent=2))
    write_json_atomic(out_dir / "metrics.json", json.dumps(metrics, indent=2, default=str))
    logger.info(f"write_business_results: {business_id} -> {out_dir}")


SUMMARY_COLUMNS = [
    "business_id",
    "status",
    "latency_s",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "first_try_valid_rate",
    "query_success_rate",
    "judge_overall",
    "judge_tool_relevance",
    "human_report_quality",
]


def rebuild_summary() -> None:
    """Aggregate every metrics.json into summary.json + summary.csv."""
    rows = []
    for metrics_path in sorted(RESULTS_DIR.glob("*/metrics.json")):
        m = json.loads(metrics_path.read_text())
        judge = m.get("judge") or {}
        rows.append(
            {
                "business_id": m.get("business_id"),
                "status": m.get("status"),
                "latency_s": (m.get("latency") or {}).get("total_seconds"),
                "input_tokens": (m.get("tokens") or {}).get("input_tokens"),
                "output_tokens": (m.get("tokens") or {}).get("output_tokens"),
                "total_tokens": (m.get("tokens") or {}).get("total_tokens"),
                "first_try_valid_rate": (m.get("tool_selection") or {}).get("first_try_valid_rate"),
                "query_success_rate": (m.get("tool_selection") or {}).get("query_success_rate"),
                "judge_overall": judge.get("overall_quality"),
                "judge_tool_relevance": judge.get("tool_selection_relevance"),
                "human_report_quality": m.get("human_report_quality"),
            }
        )

    write_json_atomic(RESULTS_DIR / "summary.json", json.dumps(rows, indent=2))

    with open(RESULTS_DIR / "summary.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def load_dataset(only: str | None) -> list[tuple[str, str]]:
    briefs = [(p.stem, p.read_text()) for p in sorted(DATASET_DIR.glob("*.txt"))]
    if only:
        briefs = [(bid, brief) for bid, brief in briefs if bid == only]
        if not briefs:
            raise SystemExit(f"No dataset file matches --only {only}")
    return briefs


async def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Prospector evaluation suite.")
    parser.add_argument("--only", help="Run a single business id (always re-runs it)")
    parser.add_argument("--force", action="store_true", help="Re-run even if results exist")
    parser.add_argument("--skip-judge", action="store_true", help="Skip LLM-as-judge scoring")
    args = parser.parse_args()

    configure_logging(level=os.environ.get("LOG_LEVEL", "INFO"))
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    briefs = load_dataset(args.only)
    orchestrator = Orchestrator()
    await init_checkpointer()

    try:
        for business_id, brief in briefs:
            metrics_path = RESULTS_DIR / business_id / "metrics.json"
            if metrics_path.exists() and not (args.force or args.only):
                logger.info(f"main: skipping {business_id} (results exist)")
                continue

            logger.info(f"main: ===== evaluating {business_id} =====")
            try:
                outcome = await run_one(orchestrator, business_id, brief)
                metrics, report = outcome["metrics"], outcome["report"]

                if report is not None and not args.skip_judge:
                    try:
                        scores, judge_usage = await judge_report(brief, report)
                        metrics["judge"] = {
                            **scores.model_dump(),
                            "judge_tokens": judge_usage,
                        }
                    except Exception as e:
                        logger.warning(f"main: judge failed for {business_id}: {e}")
                        metrics["judge"] = {"error": str(e)}
            except Exception as e:
                logger.exception(f"main: {business_id} failed")
                metrics, report = {
                    "business_id": business_id,
                    "status": "error",
                    "thread_id": None,
                    "latency": None,
                    "tokens": None,
                    "tool_selection": None,
                    "judge": None,
                    "human_report_quality": None,
                    "follow_up_question": None,
                    "error": str(e),
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }, None

            # Write immediately so a mid-run failure doesn't lose finished work
            write_business_results(business_id, report, metrics)
            rebuild_summary()
    finally:
        await close_checkpointer()

    logger.info(f"main: done. Summary at {RESULTS_DIR / 'summary.csv'}")


if __name__ == "__main__":
    asyncio.run(main())
