"""Geographic lookup endpoints."""

from fastapi import Depends
from fastapi.routing import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import get_db, require_at_most_one
from src.core.services.zips import (
    get_region_list,
    list_cbsa_names,
    list_counties,
    list_zips,
)
from src.schemas.geography import CBSAListResponse, CountyListResponse, RegionListResponse, ZipListResponse

router = APIRouter(tags=["geography"])


@router.get("/get-regions", response_model=RegionListResponse)
async def get_regions() -> RegionListResponse:
    """Get all geographic regions and their member states."""
    return RegionListResponse(regions=get_region_list())


@router.get("/get-cbsa", response_model=CBSAListResponse)
async def get_cbsa(
    state: str | None = None,
    region: str | None = None,
    session: AsyncSession = Depends(get_db),
) -> CBSAListResponse:
    """Get CBSA (metro area) names, optionally filtered by state or region.

    Provide at most one of state or region.
    """
    require_at_most_one(state=state, region=region)
    names = await list_cbsa_names(session, state=state, region=region)
    return CBSAListResponse(cbsa_names=names)


@router.get("/get-county", response_model=CountyListResponse)
async def get_county(
    region: str | None = None,
    state: str | None = None,
    city: str | None = None,
    session: AsyncSession = Depends(get_db),
) -> CountyListResponse:
    """Get county names, optionally filtered by region, state, or city.

    Provide at most one of region, state, or city.
    """
    require_at_most_one(region=region, state=state, city=city)
    counties = await list_counties(session, region=region, state=state, city=city)
    return CountyListResponse(counties=counties)


@router.get("/get-zips", response_model=ZipListResponse)
async def get_zips(
    county: str | None = None,
    state: str | None = None,
    city: str | None = None,
    session: AsyncSession = Depends(get_db),
) -> ZipListResponse:
    """Get ZIP codes, optionally filtered by county, state, or city.

    Provide at most one of county, state, or city.
    """
    require_at_most_one(county=county, state=state, city=city)
    zips = await list_zips(session, county=county, state=state, city=city)
    return ZipListResponse(zips=zips)
