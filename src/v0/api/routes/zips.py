"""ZIP code and CBSA search API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.v0.api.deps import get_db
from src.v0.api.schemas import ZipNearbyListResponse, ZipNearbyResponse, ZipSearchResponse
from src.v0.services.zip_service import ZipService

router = APIRouter(prefix="/zips", tags=["zips"])


@router.get("/search", response_model=ZipSearchResponse)
def search_metros(
    q: str = Query(..., min_length=2, description="Search query for CBSA name"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
    db: Session = Depends(get_db),
):
    """Search for CBSA metro areas by name.

    Use this for autocomplete when selecting a metro area for site selection reports.
    """
    service = ZipService(db)
    cbsa_names = service.search_metros(q, limit=limit)
    return ZipSearchResponse(cbsa_names=cbsa_names)


@router.get("/nearby", response_model=ZipNearbyListResponse)
def get_nearby_zips(
    lat: float = Query(..., description="Center latitude"),
    lng: float = Query(..., description="Center longitude"),
    r: int = Query(5000, ge=100, le=50000, description="Radius in meters"),
    db: Session = Depends(get_db),
):
    """Get ZIP codes within a radius of a location.

    Returns basic ZIP info including population and income.
    """
    service = ZipService(db)
    zips = service.get_zips_within_radius(lat, lng, r)

    zip_responses = [
        ZipNearbyResponse(
            zip=z.zip,
            city=z.city,
            state_id=z.state_id,
            population=z.population,
            income_household_median=z.income_household_median,
        )
        for z in zips
    ]

    return ZipNearbyListResponse(zips=zip_responses, count=len(zip_responses))
