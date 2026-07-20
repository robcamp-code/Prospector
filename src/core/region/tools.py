"""Geographic lookup functions for querying distinct values from uszips table."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.region.constants import REGIONS


def get_states_by_region(region_name: str) -> list[str]:
    """Get state names for a given region.

    Example:
        get_states_by_region("south")
        -> ["Texas", "Oklahoma", ...]
    """
    region = REGIONS.get(region_name)

    if not region:
        raise ValueError(f"Unknown region: {region_name}")

    return [state.value for state in region]


# =============================================================================
# Distinct Value Queries
# =============================================================================


async def get_distinct_counties(
    session: AsyncSession,
    region: str | None = None,
    state: str | None = None,
) -> list[str]:
    """Get distinct county names.

    Args:
        session: AsyncSession for database access
        region: Optional region name to filter by
        state: Optional state name to filter by

    Returns:
        List of distinct county names

    Example:
        >>> await get_distinct_counties(session, state="Georgia")
        ["Fulton County", "DeKalb County", ...]
    """
    clauses = [
        "county_name IS NOT NULL",
        "county_name != ''",
    ]
    params: dict[str, str] = {}

    if state:
        clauses.append("state_name = :state_name")
        params["state_name"] = state
    elif region:
        states = get_states_by_region(region)
        state_list = ", ".join(f"'{s}'" for s in states)
        clauses.append(f"state_name IN ({state_list})")

    where_clause = " AND ".join(clauses)

    query = text(f"""
        SELECT DISTINCT county_name
        FROM uszips
        WHERE {where_clause}
        ORDER BY county_name
    """)

    result = await session.execute(query, params)
    return [row[0] for row in result.fetchall()]


async def get_distinct_cities(
    session: AsyncSession,
    region: str | None = None,
    state: str | None = None,
    county: str | None = None,
) -> list[str]:
    """Get distinct city names.

    Args:
        session: AsyncSession for database access
        region: Optional region name to filter by
        state: Optional state name to filter by
        county: Optional county name to filter by

    Returns:
        List of distinct city names

    Example:
        >>> await get_distinct_cities(session, state="Georgia")
        ["Atlanta", "Savannah", ...]
    """
    clauses = [
        "city IS NOT NULL",
        "city != ''",
    ]
    params: dict[str, str] = {}

    if state:
        clauses.append("state_name = :state_name")
        params["state_name"] = state
    elif region:
        states = get_states_by_region(region)
        state_list = ", ".join(f"'{s}'" for s in states)
        clauses.append(f"state_name IN ({state_list})")

    if county:
        clauses.append("county_name = :county_name")
        params["county_name"] = county

    where_clause = " AND ".join(clauses)

    query = text(f"""
        SELECT DISTINCT city
        FROM uszips
        WHERE {where_clause}
        ORDER BY city
    """)

    result = await session.execute(query, params)
    return [row[0] for row in result.fetchall()]


async def get_distinct_cbsa(
    session: AsyncSession,
    region: str | None = None,
    state: str | None = None,
) -> list[str]:
    """Get distinct CBSA (metro area) names.

    Args:
        session: AsyncSession for database access
        region: Optional region name to filter by
        state: Optional state name to filter by

    Returns:
        List of distinct CBSA names

    Example:
        >>> await get_distinct_cbsa(session, state="Georgia")
        ["Atlanta-Sandy Springs-Alpharetta, GA", ...]
    """
    clauses = [
        "cbsa_name IS NOT NULL",
        "cbsa_name != ''",
    ]
    params: dict[str, str] = {}

    if state:
        clauses.append("state_name = :state_name")
        params["state_name"] = state
    elif region:
        states = get_states_by_region(region)
        state_list = ", ".join(f"'{s}'" for s in states)
        clauses.append(f"state_name IN ({state_list})")

    where_clause = " AND ".join(clauses)

    query = text(f"""
        SELECT DISTINCT cbsa_name
        FROM uszips
        WHERE {where_clause}
        ORDER BY cbsa_name
    """)

    result = await session.execute(query, params)
    return [row[0] for row in result.fetchall()]


# =============================================================================
# Top N Queries (ordered by aggregated column)
# =============================================================================


async def get_top_counties(
    session: AsyncSession,
    order_by: str = "population",
    limit: int = 10,
    region: str | None = None,
    state: str | None = None,
    desc: bool = True,
) -> list[dict[str, str | float]]:
    """Get top N counties ordered by an aggregated column.

    Args:
        session: AsyncSession for database access
        order_by: Column to order by (e.g., "population", "density")
        limit: Number of results to return (default: 10)
        region: Optional region name to filter by
        state: Optional state name to filter by
        desc: Order descending if True (default), ascending if False

    Returns:
        List of dicts with county_name, state_name, and the ordered column value

    Example:
        >>> await get_top_counties(session, order_by="population", limit=5, state="Georgia")
        [{"county_name": "Fulton County", "state_name": "Georgia", "population": 1066710}, ...]
    """
    clauses = [
        "population > 0",
        "county_name IS NOT NULL",
        "county_name != ''",
    ]
    params: dict[str, str | int] = {"limit": limit}

    if state:
        clauses.append("state_name = :state_name")
        params["state_name"] = state
    elif region:
        states = get_states_by_region(region)
        state_list = ", ".join(f"'{s}'" for s in states)
        clauses.append(f"state_name IN ({state_list})")

    where_clause = " AND ".join(clauses)
    direction = "DESC" if desc else "ASC"

    query = text(f"""
        SELECT county_name, state_name, SUM({order_by}) AS {order_by}
        FROM uszips
        WHERE {where_clause}
        GROUP BY county_name, state_name
        ORDER BY {order_by} {direction}
        LIMIT :limit
    """)

    result = await session.execute(query, params)
    return [
        {"county_name": row[0], "state_name": row[1], order_by: row[2]}
        for row in result.fetchall()
    ]


async def get_top_cities(
    session: AsyncSession,
    order_by: str = "population",
    limit: int = 10,
    region: str | None = None,
    state: str | None = None,
    county: str | None = None,
    cbsa: str | None = None,
    desc: bool = True,
) -> list[dict[str, str | float]]:
    """Get top N cities ordered by an aggregated column.

    Args:
        session: AsyncSession for database access
        order_by: Column to order by (e.g., "population", "density")
        limit: Number of results to return (default: 10)
        region: Optional region name to filter by
        state: Optional state name to filter by
        county: Optional county name to filter by
        cbsa: Optional CBSA name to filter by
        desc: Order descending if True (default), ascending if False

    Returns:
        List of dicts with city, state_name, and the ordered column value

    Example:
        >>> await get_top_cities(session, order_by="population", limit=5, state="Texas")
        [{"city": "Houston", "state_name": "Texas", "population": 2304580}, ...]
    """
    clauses = [
        "population > 0",
        "city IS NOT NULL",
        "city != ''",
    ]
    params: dict[str, str | int] = {"limit": limit}

    if state:
        clauses.append("state_name = :state_name")
        params["state_name"] = state
    elif region:
        states = get_states_by_region(region)
        state_list = ", ".join(f"'{s}'" for s in states)
        clauses.append(f"state_name IN ({state_list})")

    if county:
        clauses.append("county_name = :county_name")
        params["county_name"] = county

    if cbsa:
        clauses.append("cbsa_name = :cbsa_name")
        params["cbsa_name"] = cbsa

    where_clause = " AND ".join(clauses)
    direction = "DESC" if desc else "ASC"

    query = text(f"""
        SELECT city, state_name, SUM({order_by}) AS {order_by}
        FROM uszips
        WHERE {where_clause}
        GROUP BY city, state_name
        ORDER BY {order_by} {direction}
        LIMIT :limit
    """)

    result = await session.execute(query, params)
    return [
        {"city": row[0], "state_name": row[1], order_by: row[2]}
        for row in result.fetchall()
    ]


async def get_top_cbsa(
    session: AsyncSession,
    order_by: str = "population",
    limit: int = 10,
    region: str | None = None,
    state: str | None = None,
    desc: bool = True,
) -> list[dict[str, str | float]]:
    """Get top N CBSAs (metro areas) ordered by an aggregated column.

    Args:
        session: AsyncSession for database access
        order_by: Column to order by (e.g., "population", "density")
        limit: Number of results to return (default: 10)
        region: Optional region name to filter by
        state: Optional state name to filter by
        desc: Order descending if True (default), ascending if False

    Returns:
        List of dicts with cbsa_name and the ordered column value

    Example:
        >>> await get_top_cbsa(session, order_by="population", limit=5)
        [{"cbsa_name": "New York-Newark-Jersey City, NY-NJ-PA", "population": 19979477}, ...]
    """
    clauses = [
        "population > 0",
        "cbsa_name IS NOT NULL",
        "cbsa_name != ''",
    ]
    params: dict[str, str | int] = {"limit": limit}

    if state:
        clauses.append("state_name = :state_name")
        params["state_name"] = state
    elif region:
        states = get_states_by_region(region)
        state_list = ", ".join(f"'{s}'" for s in states)
        clauses.append(f"state_name IN ({state_list})")

    where_clause = " AND ".join(clauses)
    direction = "DESC" if desc else "ASC"

    query = text(f"""
        SELECT cbsa_name, SUM({order_by}) AS {order_by}
        FROM uszips
        WHERE {where_clause}
        GROUP BY cbsa_name
        ORDER BY {order_by} {direction}
        LIMIT :limit
    """)

    result = await session.execute(query, params)
    return [{"cbsa_name": row[0], order_by: row[1]} for row in result.fetchall()]


# =============================================================================
# CBSA Name Resolution
# =============================================================================


async def lookup_cbsa_names(
    session: AsyncSession,
    search_terms: list[str],
) -> list[str]:
    """Resolve user-provided metro names to actual CBSA names in database.

    Performs fuzzy matching using ILIKE prefix search against the uszips table.

    Args:
        session: Database session
        search_terms: User-provided names like ["New York", "Los Angeles", "Miami"]

    Returns:
        List of matching CBSA names from database (may be fewer than input
        if some terms don't match)

    Example:
        >>> await lookup_cbsa_names(session, ["New York", "Los Angeles", "Miami"])
        ["New York-Newark-Jersey City, NY-NJ-PA",
         "Los Angeles-Long Beach-Anaheim, CA",
         "Miami-Fort Lauderdale-Pompano Beach, FL"]
    """
    results: list[str] = []

    for term in search_terms:
        query = text("""
            SELECT DISTINCT cbsa_name
            FROM uszips
            WHERE cbsa_name ILIKE :pattern
            AND population > 0
            ORDER BY cbsa_name
            LIMIT 1
        """)
        result = await session.execute(query, {"pattern": f"{term}%"})
        cbsa = result.scalar()

        if cbsa:
            results.append(cbsa)

    return results
