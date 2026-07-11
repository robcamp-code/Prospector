"""Instagram search tools using Apify."""

import json

from apify_client import ApifyClient
from langchain.tools import tool

from src.config import APIFY_API_KEY
from src.models.results import InstagramProfileResult


@tool
def search_ig_profiles(query: str, live_search: bool = True) -> str:
    """
    Search Instagram for profiles based on a search query.

    Args:
        query: Search query for finding Instagram profiles
        live_search: Whether to use live search (default True)

    Returns:
        JSON string of filtered profile results
    """
    print(f"[search_ig_profiles] Searching for: {query}")
    apify_client = ApifyClient(APIFY_API_KEY)

    actor_client = apify_client.actor("apify/instagram-search-scraper")
    input_data = {
        "enhanceUserSearchWithFacebookPage": False,
        "liveSearch": live_search,
        "search": query,
        "searchLimit": 10,
        "searchType": "user",
    }
    profiles = actor_client.call(run_input=input_data)

    if profiles is None:
        print("[search_ig_profiles] Could not fetch profiles.")
        return "Could not fetch profiles."

    # Fetch results from the Actor run's default dataset
    dataset_client = apify_client.dataset(profiles.default_dataset_id)
    list_items_result = dataset_client.list_items()

    # Filter to CRM-relevant fields only
    filtered = []
    for item in list_items_result.items:
        try:
            profile = InstagramProfileResult.model_validate(item)
            filtered.append(profile.model_dump(by_alias=False))
        except Exception:
            pass

    print(f"[search_ig_profiles] Found {len(filtered)} profiles")
    return json.dumps(filtered, indent=2)
