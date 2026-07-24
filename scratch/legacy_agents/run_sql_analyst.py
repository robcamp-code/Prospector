#!/usr/bin/env python3
"""Script to test the SQL Analyst Agent."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.sql_analyst import SQLAnalystAgent


async def main():
    """Run the SQL Analyst Agent for testing."""
    # Default test parameters
    profile_id = 1
    target_geography = "Atlanta-Sandy Springs-Alpharetta, GA"
    geography_type = "cbsa"

    # Allow command line overrides
    if len(sys.argv) > 1:
        profile_id = int(sys.argv[1])
    if len(sys.argv) > 2:
        target_geography = sys.argv[2]
    if len(sys.argv) > 3:
        geography_type = sys.argv[3]

    print("=" * 60)
    print("SQL Analyst Agent Test")
    print("=" * 60)
    print(f"Profile ID: {profile_id}")
    print(f"Target Geography: {target_geography}")
    print(f"Geography Type: {geography_type}")
    print("=" * 60)

    agent = SQLAnalystAgent()

    print("\nRunning analysis (without checkpointer for testing)...")
    result = await agent.run_without_checkpointer(
        profile_id=profile_id,
        target_geography=target_geography,
        geography_type=geography_type,
    )

    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)

    analysis_result = result.get("analysis_result")
    if analysis_result is None:
        print("ERROR: No analysis result returned")
        return

    # Convert to dict for display
    result_dict = (
        analysis_result.model_dump()
        if hasattr(analysis_result, "model_dump")
        else analysis_result
    )

    print(f"\nProfile: {result_dict['profile_name']} (ID: {result_dict['profile_id']})")
    print(f"Target: {result_dict['target_geography']} ({result_dict['geography_type']})")
    print(f"Total ZIPs: {result_dict['total_zips_analyzed']:,}")
    print(f"Total Population: {result_dict['total_population']:,.0f}")

    print("\n--- Top Counties ---")
    for loc in result_dict.get("top_counties", []):
        print(
            f"  {loc['rank']}. {loc['name']} - Score: {loc['score']:.1f}, "
            f"Pop: {loc['population']:,.0f}, Income: ${loc['median_income']:,.0f}"
        )

    print("\n--- Top Cities ---")
    for loc in result_dict.get("top_cities", []):
        print(
            f"  {loc['rank']}. {loc['name']} - Score: {loc['score']:.1f}, "
            f"Pop: {loc['population']:,.0f}, Income: ${loc['median_income']:,.0f}"
        )

    print("\n--- Top ZIP Codes ---")
    for loc in result_dict.get("top_zips", []):
        print(
            f"  {loc['rank']}. {loc['name']} - Score: {loc['score']:.1f}, "
            f"Pop: {loc['population']:,.0f}, Income: ${loc['median_income']:,.0f}"
        )

    print("\n" + "=" * 60)
    print("Analysis complete!")


if __name__ == "__main__":
    asyncio.run(main())
