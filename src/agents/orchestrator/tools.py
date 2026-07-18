"""Tools for the orchestrator agent."""

from uuid import uuid4

from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.types import Command
from sqlalchemy.orm import Session
from typing_extensions import Annotated

from src.agents.sql_analyst import SQLAnalystAgent
from src.agents.sql_analyst.models import AnalysisResult
from src.agents.user_persona import UserPersonaAgent
from src.models.base import SessionLocal
from src.models.profiles import ClientProfile
from src.models.state_models import ClientProfileRef


def _extract_profile_id(result: dict) -> int | None:
    """Extract profile_id from UserPersonaAgent result.

    The UserPersonaAgent returns a dict with:
    - profile_id: The ID directly at top level
    - state: The full accumulated state values

    Args:
        result: The result dict from UserPersonaAgent.run()

    Returns:
        The extracted profile ID, or None if not found
    """
    # Check for profile_id at top level (new format)
    if "profile_id" in result and result["profile_id"] is not None:
        print(f"[Orchestrator] Found profile_id at top level: {result['profile_id']}")
        return result["profile_id"]

    # Check in state values (new format)
    if "state" in result and isinstance(result["state"], dict):
        if "profile_id" in result["state"] and result["state"]["profile_id"] is not None:
            print(f"[Orchestrator] Found profile_id in state: {result['state']['profile_id']}")
            return result["state"]["profile_id"]

    # Fallback: check any nested dict for profile_id
    for key in result:
        if isinstance(result[key], dict):
            if "profile_id" in result[key] and result[key]["profile_id"] is not None:
                print(f"[Orchestrator] Found profile_id in {key}: {result[key]['profile_id']}")
                return result[key]["profile_id"]

    print(f"[Orchestrator] Could not find profile_id in result: {result}")
    return None


def _fetch_profile_ref(profile_id: int) -> ClientProfileRef | None:
    """Fetch a ClientProfile from the database and convert to ClientProfileRef.

    Args:
        profile_id: The database ID of the profile to fetch

    Returns:
        ClientProfileRef with cached fields, or None if not found
    """
    session: Session = SessionLocal()
    try:
        profile = session.query(ClientProfile).filter(ClientProfile.id == profile_id).first()
        if profile is None:
            return None

        return ClientProfileRef(
            profile_id=profile.id,
            name=profile.name,
            business_type=profile.business_type,
            service_description=profile.service_description,
            competitor_types=profile.competitor_types or [],
            complimentary_types=profile.complimentary_types or [],
            target_income_min=profile.target_income_min,
            target_income_max=profile.target_income_max,
            target_age_min=profile.target_age_min,
            target_age_max=profile.target_age_max,
        )
    finally:
        session.close()


@tool
async def build_client_profile(
    business_description: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Analyze a business description and create a client profile.

    This tool invokes the UserPersonaAgent subagent to:
    1. Analyze the business and identify ideal customer demographics
    2. Determine competitor and complementary place types
    3. Save the complete ClientProfile to the database
    4. Update orchestrator state with the profile reference

    Args:
        business_description: Natural language description of the business,
            including type, services, target market, location, etc.

    Returns:
        Command to update orchestrator state with the new client_profile
    """

    # Create UserPersonaAgent with isolated thread
    agent = UserPersonaAgent()
    thread_id = f"user-persona-{uuid4().hex[:8]}"

    print(f"[Orchestrator] Invoking UserPersonaAgent with thread_id: {thread_id}")
    result = await agent.run(business_description, thread_id)

    # Extract profile_id from the result
    profile_id = _extract_profile_id(result)

    if profile_id is None:
        error_msg = "Failed to create client profile - could not extract profile ID from subagent result"
        print(f"[Orchestrator] ERROR: {error_msg}")
        return Command(
            update={
                "messages": [ToolMessage(content=error_msg, tool_call_id=tool_call_id)],
            }
        )

    # Fetch the profile from DB and create reference
    profile_ref = _fetch_profile_ref(profile_id)

    if profile_ref is None:
        error_msg = f"Failed to fetch client profile with ID {profile_id} from database"
        print(f"[Orchestrator] ERROR: {error_msg}")
        return Command(
            update={
                "messages": [ToolMessage(content=error_msg, tool_call_id=tool_call_id)],
            }
        )

    # Build success message
    success_msg = f"""Successfully created client profile!

**Profile ID:** {profile_ref.profile_id}
**Business:** {profile_ref.name}
**Type:** {profile_ref.business_type}

**Target Demographics:**
- Income: ${profile_ref.target_income_min:,} - ${profile_ref.target_income_max:,}
- Age: {profile_ref.target_age_min} - {profile_ref.target_age_max}

**Competitor Types:** {', '.join(profile_ref.competitor_types[:5])}{'...' if len(profile_ref.competitor_types) > 5 else ''}
**Complementary Types:** {', '.join(profile_ref.complimentary_types[:5])}{'...' if len(profile_ref.complimentary_types) > 5 else ''}
"""

    print(f"[Orchestrator] Successfully created profile {profile_ref.profile_id}")

    return Command(
        update={
            "client_profile": profile_ref,
            "messages": [ToolMessage(content=success_msg, tool_call_id=tool_call_id)],
        }
    )


@tool
def read_client_profile() -> str:
    """Read the current client profile from orchestrator state.

    This tool retrieves the currently loaded client profile, if any.
    Use this to review the profile details or confirm what profile is active.

    Note: This tool accesses the orchestrator state directly via the
    tool's injected state. The actual state access happens in the agent.

    Returns:
        String representation of the current client profile, or a message
        indicating no profile is loaded.
    """
    # This is a placeholder - the actual implementation reads from state
    # The agent will handle injecting state into this tool
    return "No client profile currently loaded. Use build_client_profile to create one or get_profile_from_db to load an existing one."


@tool
def get_profile_from_db(
    profile_id: int,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Load an existing client profile from the database into orchestrator state.

    Use this tool when a user wants to work with a previously created profile.

    Args:
        profile_id: The database ID of the profile to load

    Returns:
        Command to update orchestrator state with the loaded profile
    """

    profile_ref = _fetch_profile_ref(profile_id)

    if profile_ref is None:
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=f"Profile with ID {profile_id} not found in database.",
                        tool_call_id=tool_call_id,
                    )
                ],
            }
        )

    success_msg = f"""Loaded client profile from database!

**Profile ID:** {profile_ref.profile_id}
**Business:** {profile_ref.name}
**Type:** {profile_ref.business_type}

**Target Demographics:**
- Income: ${profile_ref.target_income_min:,} - ${profile_ref.target_income_max:,}
- Age: {profile_ref.target_age_min} - {profile_ref.target_age_max}

**Competitor Types:** {', '.join(profile_ref.competitor_types[:5])}{'...' if len(profile_ref.competitor_types) > 5 else ''}
**Complementary Types:** {', '.join(profile_ref.complimentary_types[:5])}{'...' if len(profile_ref.complimentary_types) > 5 else ''}
"""

    return Command(
        update={
            "client_profile": profile_ref,
            "messages": [ToolMessage(content=success_msg, tool_call_id=tool_call_id)],
        }
    )


@tool
async def analyze_geography(
    profile_id: Annotated[int, "ID of the ClientProfile to use for scoring"],
    geography_type: Annotated[str, "Type of geography: 'cbsa' (metro area) or 'state'"],
    geography_value: Annotated[str, "Name of the geography to analyze (e.g., 'Atlanta-Sandy Springs-Alpharetta, GA' or 'Georgia')"],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Analyze a geographic area to find the best locations matching a client profile.

    This tool invokes the SQLAnalystAgent subagent to:
    1. Fetch all ZIP codes in the target geography (CBSA metro area or state)
    2. Score each ZIP against the client profile's ideal customer demographics
    3. Aggregate and rank locations at multiple levels (state → cbsa → county → city → zip)
    4. Return the top 5 best-matching locations at each geographic level

    The analysis considers:
    - Target income range alignment
    - Target age range alignment
    - Home ownership rates
    - Education levels

    Args:
        profile_id: Database ID of the ClientProfile to use for demographic matching
        geography_type: Either 'cbsa' for metro areas or 'state' for states
        geography_value: Name of the geography (must match database exactly)

    Returns:
        Command to update orchestrator state with the AnalysisResult
    """
    # Create SQLAnalystAgent with isolated thread
    agent = SQLAnalystAgent()
    thread_id = f"sql-analyst-{uuid4().hex[:8]}"

    print(f"[Orchestrator] Invoking SQLAnalystAgent with thread_id: {thread_id}")
    print(f"[Orchestrator] Analyzing {geography_type}: {geography_value} for profile {profile_id}")

    try:
        result = await agent.run(
            profile_id=profile_id,
            target_geography=geography_value,
            geography_type=geography_type,
            thread_id=thread_id,
        )

        analysis_result = result.get("analysis_result")

        if analysis_result is None:
            error_msg = "Analysis did not complete successfully - no results returned"
            print(f"[Orchestrator] ERROR: {error_msg}")
            return Command(
                update={
                    "messages": [ToolMessage(content=error_msg, tool_call_id=tool_call_id)],
                }
            )

        # Build success message with key findings
        result_dict = (
            analysis_result.model_dump()
            if hasattr(analysis_result, "model_dump")
            else analysis_result
        )

        # Format top locations
        def format_locations(locations: list, level: str) -> str:
            if not locations:
                return f"No {level} data available"
            lines = []
            for loc in locations[:3]:
                lines.append(
                    f"  {loc['rank']}. **{loc['name']}** - Score: {loc['score']:.1f}, "
                    f"Pop: {loc['population']:,.0f}, Income: ${loc['median_income']:,.0f}"
                )
            return "\n".join(lines)

        success_msg = f"""Geographic analysis complete!

**Analysis Summary:**
- Profile: {result_dict['profile_name']} (ID: {result_dict['profile_id']})
- Target: {result_dict['target_geography']} ({result_dict['geography_type']})
- ZIPs Analyzed: {result_dict['total_zips_analyzed']:,}
- Total Population: {result_dict['total_population']:,.0f}

**Top Counties:**
{format_locations(result_dict.get('top_counties', []), 'county')}

**Top Cities:**
{format_locations(result_dict.get('top_cities', []), 'city')}

**Top ZIP Codes:**
{format_locations(result_dict.get('top_zips', []), 'ZIP')}
"""

        print(f"[Orchestrator] Analysis complete for {geography_value}")

        return Command(
            update={
                "analysis_result": analysis_result,
                "target_location": geography_value,
                "messages": [ToolMessage(content=success_msg, tool_call_id=tool_call_id)],
            }
        )

    except Exception as e:
        error_msg = f"Error during geographic analysis: {str(e)}"
        print(f"[Orchestrator] ERROR: {error_msg}")
        import traceback
        traceback.print_exc()
        return Command(
            update={
                "messages": [ToolMessage(content=error_msg, tool_call_id=tool_call_id)],
            }
        )


# List of all orchestrator tools
ORCHESTRATOR_TOOLS = [
    build_client_profile,
    read_client_profile,
    get_profile_from_db,
    analyze_geography,
]
