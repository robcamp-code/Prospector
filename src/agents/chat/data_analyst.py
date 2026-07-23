"""Data Analyst node: resolve location, select categories and geography level."""

from langchain_anthropic import ChatAnthropic

from src.core.demographics import DEMOGRAPHICS
from src.agents.chat.graph_state import GraphState, AnalysisPlan
from src.agents.chat.location_filters import LocationFilters
from src.agents.chat.prompts import LOCATION_EXTRACTION_PROMPT
from src.core.config import get_settings

CORE_CATEGORIES = ["income", "age", "education"]


async def data_analyst(state: GraphState, config: dict) -> dict:
    """Transform profile into a query plan: location filters, categories, geography level.

    No tool calls, pure LLM + deterministic logic.
    """
    model_id = get_settings().model.split(":", 1)[-1]  # Extract from "provider:model-id"
    llm = ChatAnthropic(model=model_id)
    profile = state["client_profile"]

    # Step 1: Resolve location preference text into structured filters via LLM
    extraction_prompt = f"""{LOCATION_EXTRACTION_PROMPT}

Client's raw location preference: "{profile.location_preference}"

Extract the location filters from this preference."""

    location_filters = await llm.with_structured_output(LocationFilters).ainvoke([
        {"role": "system", "content": extraction_prompt},
    ])

    # Step 2: Select categories deterministically
    categories = _select_categories(profile)

    # Step 3: Pick geography_level based on location scope
    geography_level = _pick_geography_level(location_filters.scope)

    # Step 4: Build AnalysisPlan
    plan = AnalysisPlan(
        location=location_filters.model_dump(),
        categories=categories,
        geography_level=geography_level,
        reasoning=f"Resolved location to {location_filters.scope} scope, "
                  f"selected {len(categories)} categories for {profile.business_type}, "
                  f"will group results by {geography_level}.",
    )

    return {"analysis_plan": plan}


def _select_categories(profile) -> list[str]:
    """Select categories based on profile's demographic targets and core categories.

    Algorithm:
    1. Map each target's demographic_key -> CategoryName via DEMOGRAPHICS
    2. Union with CORE_CATEGORIES
    3. Pad to minimum count using category priority order
    4. Fall back to all categories if no mapping succeeded
    """
    categories_set = set()

    # Step 1: Map demographic targets to categories
    for target in profile.target_demographics:
        category = DEMOGRAPHICS.category_for_metric(target.demographic_key)
        if category:
            categories_set.add(category)

    # Step 2: Add core categories
    categories_set.update(CORE_CATEGORIES)

    # Step 3: Convert to list and pad to minimum
    selected = list(categories_set)
    min_count = 5

    if len(selected) < min_count:
        # Pad with categories from priority order, avoiding duplicates
        all_categories = DEMOGRAPHICS.get_all_categories()
        for cat in all_categories:
            if cat not in selected:
                selected.append(cat)
                if len(selected) >= min_count:
                    break

    # Step 4: Fall back to all if nothing was selected
    if not selected:
        selected = DEMOGRAPHICS.get_all_categories()

    return selected


def _pick_geography_level(scope: str) -> str:
    """Deterministically pick geography_level based on location scope.

    Rationale: always group one level below the filter so results are chartable.
    """
    scope_to_level = {
        "nationwide": "state",          # Group by state when filtering nationwide
        "region": "state",               # Group by state when filtering by region
        "states": "county",              # Group by county when filtering by states
        "metros": "zip",                 # Group by zip when filtering by metros (user can drill down)
    }
    return scope_to_level.get(scope, "state")  # Default to state
