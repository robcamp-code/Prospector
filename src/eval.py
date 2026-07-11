"""
Evaluation script for Prospector system.
Runs test.csv through the pipeline and measures results.
"""

import csv
import time
from pathlib import Path

from src.main import run


def evaluate(input_csv: str, output_csv: str) -> None:
    """
    Run evaluation on test dataset and output results.

    Args:
        input_csv: Path to input CSV file (test.csv)
        output_csv: Path to output results CSV file
    """
    results = []
    input_path = Path(input_csv)
    output_path = Path(output_csv)

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Reading test data from: {input_path}")
    print("=" * 60)

    with open(input_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total_rows = len(rows)
    print(f"Found {total_rows} test rows\n")

    for idx, row in enumerate(rows, 1):
        category = row.get("category", "unknown")
        niche = row.get("niche", "unknown")
        size = row.get("size", "unknown")

        print(f"[{idx}/{total_rows}] Processing: {category} / {niche} / {size}")

        start = time.time()
        try:
            leads = run(row, index=idx)
            execution_time = time.time() - start

            # Count leads by source
            instagram_count = sum(1 for lead in leads if lead.source == "instagram")
            youtube_count = sum(1 for lead in leads if lead.source == "youtube")
            google_maps_count = sum(1 for lead in leads if lead.source == "google_maps")

            result = {
                "category": category,
                "niche": niche,
                "size": size,
                "lead_count": len(leads),
                "instagram_count": instagram_count,
                "youtube_count": youtube_count,
                "google_maps_count": google_maps_count,
                "execution_time": round(execution_time, 2),
                "success": True,
                "error": None,
            }
            print(f"    Found {len(leads)} leads in {execution_time:.1f}s")

        except Exception as e:
            execution_time = time.time() - start
            result = {
                "category": category,
                "niche": niche,
                "size": size,
                "lead_count": 0,
                "instagram_count": 0,
                "youtube_count": 0,
                "google_maps_count": 0,
                "execution_time": round(execution_time, 2),
                "success": False,
                "error": str(e),
            }
            print(f"    ERROR: {e}")

        results.append(result)

    # Write results CSV
    print("\n" + "=" * 60)
    print(f"Writing results to: {output_path}")

    fieldnames = [
        "category",
        "niche",
        "size",
        "lead_count",
        "instagram_count",
        "youtube_count",
        "google_maps_count",
        "execution_time",
        "success",
        "error",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    # Print summary statistics
    print_summary(results)


def print_summary(results: list[dict]) -> None:
    """Print summary statistics for the evaluation run."""
    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)

    total_rows = len(results)
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    # Success rate
    success_rate = (len(successful) / total_rows * 100) if total_rows > 0 else 0
    print(f"\nSuccess Rate: {len(successful)}/{total_rows} ({success_rate:.1f}%)")

    if successful:
        # Lead statistics
        total_leads = sum(r["lead_count"] for r in successful)
        avg_leads = total_leads / len(successful)
        print(f"\nTotal Leads: {total_leads}")
        print(f"Average Leads per Row: {avg_leads:.1f}")

        # Leads by source
        total_instagram = sum(r["instagram_count"] for r in successful)
        total_youtube = sum(r["youtube_count"] for r in successful)
        total_google_maps = sum(r["google_maps_count"] for r in successful)

        print(f"\nLeads by Source:")
        print(f"  Instagram:   {total_instagram}")
        print(f"  YouTube:     {total_youtube}")
        print(f"  Google Maps: {total_google_maps}")

        # Execution time
        total_time = sum(r["execution_time"] for r in successful)
        avg_time = total_time / len(successful)
        print(f"\nExecution Time:")
        print(f"  Total:   {total_time:.1f}s")
        print(f"  Average: {avg_time:.1f}s per row")

    # Failed cases
    if failed:
        print(f"\nFailed Cases ({len(failed)}):")
        for r in failed:
            print(f"  - {r['category']}/{r['niche']}/{r['size']}: {r['error']}")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    evaluate("evals/test.csv", "evals/results.csv")
