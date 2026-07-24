"""Pure utilities for ZIP code aggregation."""

from sqlalchemy import func
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql import ColumnElement


def nan_safe(col: InstrumentedAttribute) -> ColumnElement:
    """Guard against NaN sentinels: COALESCE(NULLIF(col, NaN), 0).

    Relies on asyncpg parameter binding preserving NaN as Postgres NaN,
    and Postgres's non-IEEE754 equality check (NaN = NaN -> TRUE).
    Verified empirically in dev against known-NaN rows in race_white, etc.
    """
    return func.coalesce(func.nullif(col, float("nan")), 0)


def get_group_field_name(col: InstrumentedAttribute) -> str:
    """Extract the key name for a column attribute."""
    return col.key
