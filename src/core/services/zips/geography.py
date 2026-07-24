"""Geographic lookup functions for ZIP codes."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import USZip
from src.core.region.constants import REGIONS
from src.schemas.geography import RegionInfo
from src.core.services.zips.filters import GeographicFilters


async def list_cbsa_names(
    session: AsyncSession, state: str | None = None, region: str | None = None
) -> list[str]:
    """Get distinct CBSA (metro area) names."""
    stmt = (
        select(USZip.cbsa_name)
        .where(USZip.cbsa_name.is_not(None), USZip.cbsa_name != "")
        .distinct()
        .order_by(USZip.cbsa_name)
    )
    filters = GeographicFilters(state=state, region=region)
    stmt = filters.apply_to_geography_query(stmt)
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]


async def list_counties(
    session: AsyncSession,
    region: str | None = None,
    state: str | None = None,
    city: str | None = None,
) -> list[str]:
    """Get distinct county names."""
    stmt = (
        select(USZip.county_name)
        .where(USZip.county_name.is_not(None), USZip.county_name != "")
        .distinct()
        .order_by(USZip.county_name)
    )
    filters = GeographicFilters(state=state, region=region)
    stmt = filters.apply_to_geography_query(stmt)
    if city:
        stmt = stmt.where(USZip.city == city)
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]


async def list_zips(
    session: AsyncSession,
    county: str | None = None,
    state: str | None = None,
    city: str | None = None,
) -> list[str]:
    """Get distinct zip codes."""
    stmt = select(USZip.zip).where(USZip.zip.is_not(None)).distinct().order_by(USZip.zip)
    filters = GeographicFilters(state=state, county=county)
    stmt = filters.apply_to_geography_query(stmt)
    if city:
        stmt = stmt.where(USZip.city == city)
    result = await session.execute(stmt)
    return [row[0] for row in result.all()]


def get_region_list() -> list[RegionInfo]:
    """Get all regions with their member states."""
    return [
        RegionInfo(
            key=key,
            display_name=key.replace("_", " ").title(),
            states=[state.value for state in enum_cls],
        )
        for key, enum_cls in REGIONS.items()
    ]
