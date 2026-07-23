"""Geographic filter composition for ZIP aggregations."""

from fastapi import HTTPException
from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.selectable import Select

from src.core.database import USZip
from src.core.region.tools import get_states_by_region


class GeographicFilters:
    """Encapsulates geographic filter state (state, region, county, cbsa, city)."""

    def __init__(
        self,
        state: str | None = None,
        region: str | None = None,
        county: str | None = None,
        cbsa: str | None = None,
        city: str | None = None,
    ):
        self.state = state
        self.region = region
        self.county = county
        self.cbsa = cbsa
        self.city = city

    def apply_to_statement(self, stmt: Select) -> Select:
        """Apply all filters to a SQLAlchemy select statement."""
        # State or region (mutually exclusive at this layer, but both applied)
        if self.state:
            stmt = stmt.where(USZip.state_name == self.state)
        if self.region:
            try:
                states = get_states_by_region(self.region)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            stmt = stmt.where(USZip.state_name.in_(states))

        # County, CBSA, city (additive filters)
        if self.county:
            stmt = stmt.where(USZip.county_name == self.county)
        if self.cbsa:
            stmt = stmt.where(USZip.cbsa_name == self.cbsa)
        if self.city:
            stmt = stmt.where(USZip.city == self.city)

        return stmt

    def apply_to_geography_query(self, stmt: Select) -> Select:
        """Apply state/region filters only (for geography discovery queries)."""
        if self.state:
            stmt = stmt.where(USZip.state_name == self.state)
        if self.region:
            try:
                states = get_states_by_region(self.region)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            stmt = stmt.where(USZip.state_name.in_(states))
        return stmt
