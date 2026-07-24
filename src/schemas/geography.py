"""Geography endpoint request and response schemas."""

from pydantic import BaseModel


class RegionInfo(BaseModel):
    """Information about a region and its member states."""

    key: str
    display_name: str
    states: list[str]


class RegionListResponse(BaseModel):
    """Response for /get-regions endpoint."""

    regions: list[RegionInfo]


class CBSAListResponse(BaseModel):
    """Response for /get-cbsa endpoint."""

    cbsa_names: list[str]


class CountyListResponse(BaseModel):
    """Response for /get-county endpoint."""

    counties: list[str]


class ZipListResponse(BaseModel):
    """Response for /get-zips endpoint."""

    zips: list[str]
