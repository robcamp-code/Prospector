"""Google search tools (YouTube and Google Maps) using SerpAPI."""

import json

import serpapi

from src.config import SERPAPI_KEY, DEFAULT_LOCATION
from src.utils.geocoding import to_ll
from src.models.results import YouTubeResult, GoogleMapsResult

from langchain.tools import tool


@tool
def search_youtube(query: str, max_results: int = 10) -> str:
    """
    Search YouTube for channels and videos related to a query.

    Args:
        query: Search query for finding YouTube content
        max_results: Maximum number of results to return (default 10)

    Returns:
        JSON string of YouTube search results
    """
    print(f"[search_youtube] Searching for: {query}")
    client = serpapi.Client(api_key=SERPAPI_KEY)

    results = client.search({"engine": "youtube", "search_query": query})

    parsed_results = []

    # Parse channel results
    if "channel_results" in results:
        for channel in results["channel_results"][:max_results]:
            try:
                result = YouTubeResult(
                    title=channel.get("title", ""),
                    channel_name=channel.get("title", ""),
                    channel_url=channel.get("link"),
                    subscriber_count=channel.get("subscribers"),
                    description=channel.get("description"),
                )
                parsed_results.append(result.model_dump())
            except Exception:
                pass

    # Parse video results
    if "video_results" in results:
        for video in results["video_results"][:max_results]:
            try:
                channel_info = video.get("channel", {})
                result = YouTubeResult(
                    title=video.get("title", ""),
                    channel_name=channel_info.get("name", ""),
                    channel_url=channel_info.get("link"),
                    video_url=video.get("link"),
                    view_count=video.get("views"),
                    description=video.get("description"),
                )
                parsed_results.append(result.model_dump())
            except Exception:
                pass

    print(f"[search_youtube] Found {len(parsed_results)} results")
    return json.dumps(parsed_results, indent=2)


@tool
def search_google_maps(query: str, location: str | None = None) -> str:
    """
    Search Google Maps for businesses related to a query.

    Args:
        query: Search query for finding businesses (e.g., "coffee shop", "real estate agent")
        location: Location to search in (e.g., "Atlanta, GA"). Uses default if not provided.

    Returns:
        JSON string of Google Maps search results
    """
    search_location = location or DEFAULT_LOCATION
    print(f"[search_google_maps] Searching for: {query} in {search_location}")

    client = serpapi.Client(api_key=SERPAPI_KEY)

    try:
        ll = to_ll(search_location)
    except ValueError as e:
        print(f"[search_google_maps] Geocoding error: {e}")
        return json.dumps({"error": str(e)})

    results = client.search({"engine": "google_maps", "q": query, "ll": ll})

    parsed_results = []

    if "local_results" in results:
        for place in results["local_results"]:
            try:
                result = GoogleMapsResult(
                    name=place.get("title", ""),
                    address=place.get("address"),
                    phone=place.get("phone"),
                    website=place.get("website"),
                    google_maps_url=place.get("link"),
                    rating=place.get("rating"),
                    review_count=place.get("reviews"),
                    business_type=place.get("type"),
                )
                parsed_results.append(result.model_dump())
            except Exception:
                pass

    print(f"[search_google_maps] Found {len(parsed_results)} results")
    return json.dumps(parsed_results, indent=2)
