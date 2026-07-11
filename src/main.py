"""Main entry point for the Prospector system."""

import csv
from pathlib import Path
from uuid import uuid4

from langchain.messages import HumanMessage

from src.config import invoke_with_retry
from src.models.crm import CRMRow
from src.agents.orchestrator import create_orchestrator


def _write_crm_csv(leads: list[CRMRow], filename: str) -> None:
    """Write CRM leads to a CSV file in the crm_outputs directory."""
    if not leads:
        return

    output_dir = Path("crm_outputs")
    output_dir.mkdir(exist_ok=True)

    if not filename.endswith(".csv"):
        filename += ".csv"

    filepath = output_dir / filename
    fieldnames = list(CRMRow.model_fields.keys())

    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in leads:
            writer.writerow(row.model_dump(mode="json"))

    print(f"[run] Exported {len(leads)} leads to {filepath.absolute()}")


def run(row: dict, index: int | None = None) -> list[CRMRow]:
    """
    Run the Prospector pipeline for a single row from test.csv.

    Takes a row containing:
      - service_description: Description of the service provider
      - category: Service category (e.g., ai_automation, web_development)
      - niche: Target niche (e.g., real_estate, legal)
      - size: Business size (starter, experienced, scaling)

    Args:
        row: Dictionary containing the row data
        index: Optional row index for naming the output CSV file

    Returns:
        List of CRMRow leads discovered by the pipeline
    """
    orchestrator = create_orchestrator()

    # Build the prompt from the row data
    service_description = row.get("service_description", "")
    category = row.get("category", "")
    niche = row.get("niche", "")
    size = row.get("size", "")

    prompt = f"""Help me find leads for this service provider.

Service Description:
{service_description}

Category: {category}
Niche: {niche}
Business Size: {size}

Please:
1. Build a user persona from this description
2. Expand keywords for discovery
3. Search Instagram for relevant profiles
4. Search YouTube and Google Maps for relevant leads
5. Add all discovered leads to the CRM

Return the final list of leads found."""

    # Use unique thread ID for each run
    config = {"configurable": {"thread_id": f"prospector-{str(uuid4())}"}}

    response = invoke_with_retry(orchestrator, {"messages": [HumanMessage(prompt)]}, config)

    leads = response.get("output_crm", [])

    # Write leads to CSV in crm_outputs folder
    filename = f"{index}.csv" if index is not None else f"{config['configurable']['thread_id']}.csv"
    _write_crm_csv(leads, filename)

    return leads


if __name__ == "__main__":
    # Simple test with a sample row
    test_row = {
        "service_description": "I build simple AI-powered automations and chatbots using Python and LangChain",
        "category": "ai_automation",
        "niche": "small_business",
        "size": "starter",
    }

    leads = run(test_row, index=0)
    print(f"Found {len(leads)} leads")
    for lead in leads:
        print(f"  - {lead.name} ({lead.source})")
