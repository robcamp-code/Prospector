"""CRM management tools for adding, reading, and exporting leads."""

import csv
import json
from pathlib import Path

from langchain.tools import tool, ToolRuntime
from langchain.messages import ToolMessage
from langgraph.types import Command

from src.models.crm import CRMRow


@tool
def add_leads_to_crm(leads: list[CRMRow], runtime: ToolRuntime) -> Command:
    """Add new leads to the CRM in state."""
    current_crm = runtime.state.get("output_crm", [])
    updated_crm = current_crm + leads
    return Command(
        update={
            "output_crm": updated_crm,
            "messages": [
                ToolMessage(
                    f"Added {len(leads)} leads to CRM", tool_call_id=runtime.tool_call_id
                )
            ],
        }
    )


@tool
def read_crm(runtime: ToolRuntime) -> str:
    """Read the current CRM from state."""
    crm = runtime.state.get("output_crm", [])
    if not crm:
        return "CRM is empty. Run lead generation tools first."
    return json.dumps([row.model_dump(mode="json") for row in crm], indent=2)


@tool
def export_crm_to_csv(filename: str, runtime: ToolRuntime) -> str:
    """Export the CRM to a CSV file."""
    crm = runtime.state.get("output_crm", [])
    if not crm:
        return "CRM is empty. Nothing to export."

    # Ensure .csv extension
    if not filename.endswith(".csv"):
        filename += ".csv"

    filepath = Path(filename)

    # Get field names from CRMRow
    fieldnames = list(CRMRow.model_fields.keys())

    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in crm:
            writer.writerow(row.model_dump(mode="json"))

    return f"Exported {len(crm)} leads to {filepath.absolute()}"
