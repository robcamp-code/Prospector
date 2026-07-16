"""Report generation API routes."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from src.api.deps import get_db
from src.api.schemas import (
    ReportResponse,
    ReportWithHtmlResponse,
    SiteSelectionRequest,
    TradeAreaRequest,
)
from src.models.reports import Report
from src.services.report_service import ReportService
from src.utils.geocoding import geocode

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/site-selection", response_model=ReportWithHtmlResponse)
def generate_site_selection_report(
    request: SiteSelectionRequest,
    db: Session = Depends(get_db),
):
    """Generate a site selection report for a metro area.

    This report analyzes all ZIP codes in a CBSA metro area and ranks them
    based on how well they match the target client profile.
    """
    service = ReportService(db)
    try:
        report = service.generate_site_selection(
            profile_id=request.profile_id,
            cbsa_name=request.cbsa_name,
        )
        return report
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/trade-area", response_model=ReportWithHtmlResponse)
def generate_trade_area_report(
    request: TradeAreaRequest,
    db: Session = Depends(get_db),
):
    """Generate a trade area report for a location.

    This report analyzes the demographics and business mix within a
    specified radius of a location.

    Either provide an address (which will be geocoded) or lat/lng coordinates.
    """
    # Geocode address if provided
    lat = request.lat
    lng = request.lng
    address = request.address

    if address and (lat is None or lng is None):
        try:
            lat, lng = geocode(address)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    elif lat is None or lng is None:
        raise HTTPException(
            status_code=400,
            detail="Either address or lat/lng coordinates required",
        )

    service = ReportService(db)
    try:
        report = service.generate_trade_area(
            profile_id=request.profile_id,
            lat=lat,
            lng=lng,
            radius_m=request.radius_m,
            address=address,
        )
        return report
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{report_id}", response_model=ReportWithHtmlResponse)
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
):
    """Get a report by ID including HTML content."""
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("/{report_id}/html", response_class=HTMLResponse)
def get_report_html(
    report_id: int,
    db: Session = Depends(get_db),
):
    """Get just the HTML content of a report for direct viewing."""
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if not report.html_content:
        raise HTTPException(status_code=404, detail="Report has no HTML content")
    return HTMLResponse(content=report.html_content)
