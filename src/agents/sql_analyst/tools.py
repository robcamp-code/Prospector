"""Tools for the SQL Analyst Agent."""

from collections import defaultdict
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.agents.sql_analyst.models import AnalysisResult, RankedLocation
from src.models.base import SessionLocal
from src.models.profiles import ClientProfile
from src.models.uszips import USZip
from src.services.zip_service import ZipService


def _get_distinct_counties(zips: list[USZip]) -> set[str]:
    """Get set of distinct county keys from ZIPs."""
    return {
        f"{z.county_name}, {z.state_id}"
        for z in zips
        if z.county_name and z.state_id
    }


def _get_distinct_cbsas(zips: list[USZip]) -> set[str]:
    """Get set of distinct CBSA names from ZIPs."""
    return {z.cbsa_name for z in zips if z.cbsa_name}


def _get_distinct_cities(zips: list[USZip]) -> set[str]:
    """Get set of distinct city keys from ZIPs."""
    return {
        f"{z.city}, {z.state_id}"
        for z in zips
        if z.city and z.state_id
    }


def _get_distinct_states(zips: list[USZip]) -> set[str]:
    """Get set of distinct state names from ZIPs."""
    return {z.state_name for z in zips if z.state_name}


def _group_zips_by_hierarchy(
    zips: list[USZip],
) -> dict[str, dict[str, list[USZip]]]:
    """Group ZIP codes by geographic hierarchy with pre-validation.

    Args:
        zips: List of USZip objects

    Returns:
        Dictionary with keys 'state', 'cbsa', 'county', 'city' each containing
        a dict mapping area name to list of ZIPs
    """
    # Pre-compute distinct entities that exist in this dataset
    valid_states = _get_distinct_states(zips)
    valid_cbsas = _get_distinct_cbsas(zips)
    valid_counties = _get_distinct_counties(zips)
    valid_cities = _get_distinct_cities(zips)

    print(f"[SQLAnalyst] Found {len(valid_states)} states, {len(valid_cbsas)} CBSAs, "
          f"{len(valid_counties)} counties, {len(valid_cities)} cities")

    hierarchy: dict[str, dict[str, list[USZip]]] = {
        "state": defaultdict(list),
        "cbsa": defaultdict(list),
        "county": defaultdict(list),
        "city": defaultdict(list),
    }

    for z in zips:
        # State grouping - validate against pre-computed set
        if z.state_name and z.state_name in valid_states:
            hierarchy["state"][z.state_name].append(z)

        # CBSA grouping - validate against pre-computed set
        if z.cbsa_name and z.cbsa_name in valid_cbsas:
            hierarchy["cbsa"][z.cbsa_name].append(z)

        # County grouping - validate against pre-computed set
        if z.county_name and z.state_id:
            county_key = f"{z.county_name}, {z.state_id}"
            if county_key in valid_counties:
                hierarchy["county"][county_key].append(z)

        # City grouping - validate against pre-computed set
        if z.city and z.state_id:
            city_key = f"{z.city}, {z.state_id}"
            if city_key in valid_cities:
                hierarchy["city"][city_key].append(z)

    return hierarchy


def _score_and_rank_group(
    group: dict[str, list[USZip]],
    geo_type: str,
    zip_service: ZipService,
    profile: ClientProfile,
    top_n: int = 5,
) -> list[RankedLocation]:
    """Score and rank a group of geographic areas.

    Args:
        group: Dict mapping area name to list of ZIPs
        geo_type: Geographic type (state, cbsa, county, city)
        zip_service: ZipService for scoring and aggregation
        profile: ClientProfile for scoring
        top_n: Number of top results to return

    Returns:
        List of RankedLocation objects sorted by score descending
    """
    scored_areas: list[tuple[str, float, float, float, float, float, float, int, list[str]]] = []

    for area_name, area_zips in group.items():
        if not area_zips:
            continue

        # Score each ZIP and compute average
        scores = [zip_service.score_zip(z, profile) for z in area_zips]
        avg_score = sum(scores) / len(scores) if scores else 0

        # Aggregate demographics (population-weighted)
        demo = zip_service.aggregate_demographics(area_zips)

        # Collect ZIP codes for city level
        zip_codes = [z.zip for z in area_zips] if geo_type in ("city", "zip") else []

        scored_areas.append(
            (
                area_name,
                avg_score,
                demo.total_population,
                demo.avg_income,
                demo.avg_age,
                demo.avg_home_ownership,
                demo.avg_education,
                demo.zip_count,
                zip_codes,
            )
        )

    # Sort by score descending
    scored_areas.sort(key=lambda x: x[1], reverse=True)

    # Take top N and convert to RankedLocation
    ranked: list[RankedLocation] = []
    for i, (name, score, pop, income, age, ownership, education, zip_count, zips) in enumerate(
        scored_areas[:top_n]
    ):
        ranked.append(
            RankedLocation(
                rank=i + 1,
                geo_type=geo_type,
                name=name,
                score=round(score, 2),
                population=pop,
                median_income=round(income, 2),
                median_age=round(age, 2),
                home_ownership=round(ownership, 4),
                education_rate=round(education, 4),
                zip_count=zip_count,
                zip_codes=zips[:10] if zips else [],  # Limit to 10 zips
            )
        )

    return ranked


def _score_individual_zips(
    zips: list[USZip],
    zip_service: ZipService,
    profile: ClientProfile,
    top_n: int = 5,
) -> list[RankedLocation]:
    """Score and rank individual ZIP codes.

    Args:
        zips: List of USZip objects
        zip_service: ZipService for scoring
        profile: ClientProfile for scoring
        top_n: Number of top results to return

    Returns:
        List of RankedLocation objects sorted by score descending
    """
    # Score each ZIP
    scored_zips = zip_service.rank_zips_for_profile(zips, profile)

    # Take top N and convert to RankedLocation
    ranked: list[RankedLocation] = []
    for i, (z, score) in enumerate(scored_zips[:top_n]):
        # Build display name
        name_parts = [z.zip]
        if z.city:
            name_parts.append(z.city)
        if z.state_id:
            name_parts.append(z.state_id)
        name = ", ".join(name_parts)

        ranked.append(
            RankedLocation(
                rank=i + 1,
                geo_type="zip",
                name=name,
                score=round(score, 2),
                population=z.population or 0,
                median_income=z.income_household_median or 0,
                median_age=z.age_median or 0,
                home_ownership=z.home_ownership or 0,
                education_rate=z.education_college_or_above or 0,
                zip_count=1,
                zip_codes=[z.zip],
            )
        )

    return ranked


@tool
def aggregate_by_hierarchy(
    profile_id: Annotated[int, "ID of the ClientProfile to use for scoring"],
    geography_type: Annotated[str, "Type of geography to analyze: 'cbsa' or 'state'"],
    geography_value: Annotated[str, "Name of the CBSA or state to analyze"],
    tool_call_id: Annotated[str, InjectedToolCallId] = "",
) -> Command:
    """Analyze and rank locations by demographic alignment with a ClientProfile.

    This tool performs hierarchical demographic analysis:
    1. Fetches all ZIP codes in the target geography (CBSA or state)
    2. Scores each ZIP against the ClientProfile's ideal customer demographics
    3. Aggregates and ranks at each geographic level (state → cbsa → county → city → zip)
    4. Returns the top 5 locations at each level with demographic metrics

    Args:
        profile_id: Database ID of the ClientProfile
        geography_type: Either 'cbsa' (metro area) or 'state'
        geography_value: Name of the geography (e.g., "Atlanta-Sandy Springs-Alpharetta, GA" or "Georgia")

    Returns:
        Command with AnalysisResult in state
    """
    print("=" * 60)
    print("AGGREGATE_BY_HIERARCHY TOOL CALLED")
    print("=" * 60)
    print(f"  profile_id: {profile_id}")
    print(f"  geography_type: {geography_type}")
    print(f"  geography_value: {geography_value}")

    session: Session = SessionLocal()
    try:
        # Fetch the ClientProfile
        profile = session.query(ClientProfile).filter(ClientProfile.id == profile_id).first()
        if profile is None:
            error_msg = f"ClientProfile with ID {profile_id} not found"
            print(f"ERROR: {error_msg}")
            return Command(
                update={
                    "messages": [ToolMessage(content=error_msg, tool_call_id=tool_call_id)],
                }
            )

        print(f"  Found profile: {profile.name}")

        # Fetch ZIPs based on geography type
        zip_service = ZipService(session)

        if geography_type.lower() == "cbsa":
            zips = zip_service.get_zips_by_metro(geography_value)
        elif geography_type.lower() == "state":
            # Query ZIPs by state name
            stmt = select(USZip).where(USZip.state_name == geography_value)
            zips = list(session.execute(stmt).scalars().all())
        else:
            error_msg = f"Invalid geography_type: {geography_type}. Must be 'cbsa' or 'state'"
            print(f"ERROR: {error_msg}")
            return Command(
                update={
                    "messages": [ToolMessage(content=error_msg, tool_call_id=tool_call_id)],
                }
            )

        if not zips:
            error_msg = f"No ZIP codes found for {geography_type}: {geography_value}"
            print(f"ERROR: {error_msg}")
            return Command(
                update={
                    "messages": [ToolMessage(content=error_msg, tool_call_id=tool_call_id)],
                }
            )

        print(f"  Found {len(zips)} ZIP codes")

        # Log hierarchy distribution for debugging
        valid_counties = _get_distinct_counties(zips)
        valid_cbsas = _get_distinct_cbsas(zips)
        print(f"[SQLAnalyst] Validated {len(valid_counties)} counties and {len(valid_cbsas)} CBSAs in {geography_value}")

        # Group ZIPs by hierarchy
        groups = _group_zips_by_hierarchy(zips)

        # Score and rank at each level
        top_states = _score_and_rank_group(groups["state"], "state", zip_service, profile)
        top_cbsas = _score_and_rank_group(groups["cbsa"], "cbsa", zip_service, profile)
        top_counties = _score_and_rank_group(groups["county"], "county", zip_service, profile)
        top_cities = _score_and_rank_group(groups["city"], "city", zip_service, profile)
        top_zips = _score_individual_zips(zips, zip_service, profile)

        # Calculate summary stats
        total_population = sum(z.population or 0 for z in zips)

        # Build result
        result = AnalysisResult(
            profile_id=profile_id,
            profile_name=profile.name,
            target_geography=geography_value,
            geography_type=geography_type,
            top_states=top_states,
            top_cbsas=top_cbsas,
            top_counties=top_counties,
            top_cities=top_cities,
            top_zips=top_zips,
            total_zips_analyzed=len(zips),
            total_population=total_population,
        )

        print(f"  Analysis complete:")
        print(f"    - States: {len(top_states)}")
        print(f"    - CBSAs: {len(top_cbsas)}")
        print(f"    - Counties: {len(top_counties)}")
        print(f"    - Cities: {len(top_cities)}")
        print(f"    - ZIPs: {len(top_zips)}")
        print("=" * 60)

        # Build success message
        success_msg = f"""Analysis complete for {geography_type}: {geography_value}

**Summary:**
- Profile: {profile.name} (ID: {profile_id})
- Total ZIPs Analyzed: {len(zips):,}
- Total Population: {total_population:,.0f}

**Top Counties:**
{_format_top_locations(top_counties)}

**Top Cities:**
{_format_top_locations(top_cities)}

**Top ZIP Codes:**
{_format_top_locations(top_zips)}
"""

        return Command(
            update={
                "analysis_result": result,
                "messages": [ToolMessage(content=success_msg, tool_call_id=tool_call_id)],
            }
        )

    except Exception as e:
        error_msg = f"Error during analysis: {str(e)}"
        print(f"ERROR: {error_msg}")
        import traceback

        traceback.print_exc()
        return Command(
            update={
                "messages": [ToolMessage(content=error_msg, tool_call_id=tool_call_id)],
            }
        )
    finally:
        session.close()


def _format_top_locations(locations: list[RankedLocation]) -> str:
    """Format top locations for display."""
    if not locations:
        return "  (none)"

    lines = []
    for loc in locations[:3]:  # Show top 3 in summary
        lines.append(
            f"  {loc.rank}. {loc.name} - Score: {loc.score:.1f}, "
            f"Pop: {loc.population:,.0f}, Income: ${loc.median_income:,.0f}"
        )
    return "\n".join(lines)


# List of all tools available to the agent
TOOLS = [aggregate_by_hierarchy]
