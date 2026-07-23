"""Aggregation query builder and orchestration."""

from typing import Literal

from fastapi import HTTPException
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import USZip
from src.core.demographics import DEMOGRAPHICS, MetricType
from src.core.services.zips.filters import GeographicFilters
from src.core.services.zips.metrics import MetricColumnBuilder
from src.core.services.zips.utils import get_group_field_name, nan_safe
from src.schemas.aggregation import AggregationResponse, AggregationRow, GeographyLevel


# Column mapping for each geography level
_GROUP_BY_COLUMNS: dict[GeographyLevel, list] = {
    GeographyLevel.ZIP: [USZip.zip, USZip.city, USZip.county_name, USZip.state_name],
    GeographyLevel.COUNTY: [USZip.county_name, USZip.state_name],
    GeographyLevel.STATE: [USZip.state_name],
    GeographyLevel.CITY: [USZip.city, USZip.state_name],
    GeographyLevel.CBSA: [USZip.cbsa_name],
    GeographyLevel.REGION: [USZip.state_name],
}


def _parse_metric_selector(raw: str) -> tuple[str, str]:
    """Parse 'category.metric' string and validate against DEMOGRAPHICS."""
    parts = raw.split(".", 1)
    if len(parts) != 2:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric selector '{raw}', expected 'category.metric'",
        )
    category_str, metric_key = parts
    if category_str not in DEMOGRAPHICS.categories:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown category '{category_str}' in '{raw}'",
        )
    if metric_key not in DEMOGRAPHICS.get_category(category_str).metrics:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown metric '{metric_key}' in category '{category_str}'",
        )
    return category_str, metric_key


def _resolve_sort_label(sort_by: str, valid_labels: dict[str, any]) -> str:
    """Resolve user-facing sort_by to actual internal SQL label.

    Ensures sort_by only references columns actually in this query's SELECT,
    preventing SQL injection by restricting to user-requested metrics only.
    """
    if sort_by in ("population", "density"):
        if sort_by in valid_labels:
            return sort_by
        raise HTTPException(status_code=400, detail=f"sort_by '{sort_by}' not available")

    # Try direct __ replacement: "race.black" -> "race__black"
    candidate_flat = sort_by.replace(".", "__")
    if candidate_flat in valid_labels:
        return candidate_flat

    # Try distribution form: "race.black" might be "race__distribution__black"
    if "." in sort_by:
        category_str, subkey = sort_by.split(".", 1)
        matches = [
            l
            for l in valid_labels.keys()
            if l.startswith(f"{category_str}__") and l.endswith(f"__{subkey}")
        ]
        if len(matches) == 1:
            return matches[0]

    raise HTTPException(
        status_code=400,
        detail=f"sort_by '{sort_by}' does not match any requested metric",
    )


class AggregationQueryBuilder:
    """Orchestrates building and executing an aggregation query."""

    def __init__(
        self,
        session: AsyncSession,
        group_by: GeographyLevel,
        metric_selectors: list[str],
        sort_by: str | None = None,
        sort_dir: Literal["asc", "desc"] = "desc",
        limit: int = 50,
        offset: int = 0,
        **filter_kwargs,
    ):
        self.session = session
        self.group_by = group_by
        self.sort_by = sort_by
        self.sort_dir = sort_dir
        self.limit = limit
        self.offset = offset

        # Parse metrics and deduplicate
        parsed_metrics = [_parse_metric_selector(s) for s in metric_selectors]
        self.parsed_metrics = list(dict.fromkeys(parsed_metrics))

        # Build filters
        self.filters = GeographicFilters(
            state=filter_kwargs.get("state"),
            region=filter_kwargs.get("region"),
            county=filter_kwargs.get("county"),
            cbsa=filter_kwargs.get("cbsa"),
            city=filter_kwargs.get("city"),
        )

        # Build metric columns
        self.metric_builder = MetricColumnBuilder()
        for category, metric_key in self.parsed_metrics:
            self.metric_builder.add_metric(category, metric_key)

    def build_statement(self):
        """Build the SQLAlchemy select statement."""
        group_cols = _GROUP_BY_COLUMNS[self.group_by]

        # Population and density columns
        population_col = func.sum(nan_safe(USZip.population)).label("population")
        area_col = func.sum(
            case(
                (
                    and_(USZip.density.is_not(None), USZip.density > 0),
                    nan_safe(USZip.population) / USZip.density,
                ),
                else_=0.0,
            )
        ).label("estimated_area_km2")
        density_col = (population_col / func.nullif(area_col, 0)).label("density")

        # Build the SELECT statement
        stmt = select(
            *group_cols,
            population_col,
            density_col,
            *self.metric_builder.get_all_columns().values(),
        )

        # Apply WHERE clauses
        stmt = stmt.where(
            USZip.population.is_not(None),
            USZip.population > 0,
        )

        # Apply geographic filters
        stmt = self.filters.apply_to_statement(stmt)

        # GROUP BY and post-aggregation filter
        stmt = stmt.group_by(*group_cols)
        stmt = stmt.having(func.sum(nan_safe(USZip.population)) > 0)

        # ORDER BY (resolve sort_by to an actual label first)
        all_labels = {
            "population": population_col,
            "density": density_col,
            **self.metric_builder.get_all_columns(),
        }
        if self.sort_by:
            resolved_sort_label = _resolve_sort_label(self.sort_by, all_labels)
            sort_col = all_labels[resolved_sort_label]
        else:
            sort_col = population_col

        if self.sort_dir == "desc":
            stmt = stmt.order_by(sort_col.desc())
        else:
            stmt = stmt.order_by(sort_col.asc())

        # LIMIT and OFFSET
        stmt = stmt.limit(self.limit).offset(self.offset)

        return stmt

    async def execute(self) -> AggregationResponse:
        """Execute the query and return an AggregationResponse."""
        stmt = self.build_statement()
        result = await self.session.execute(stmt)
        rows = []

        group_cols = _GROUP_BY_COLUMNS[self.group_by]

        for row_mapping in result.mappings():
            group_dict = {
                get_group_field_name(col): row_mapping[get_group_field_name(col)]
                for col in group_cols
            }
            population = row_mapping["population"]
            density = row_mapping["density"]

            # Build metrics dict, converting internal labels back to user-facing dotted form
            metrics_dict: dict[str, float | dict[str, float]] = {}
            for (category, metric_key), labels in self.metric_builder.metric_to_labels.items():
                metric = DEMOGRAPHICS.get_metric(category, metric_key)
                user_key = f"{category}.{metric_key}"

                if metric.type == MetricType.DISTRIBUTION:
                    # Sub-keys go into a nested dict
                    sub_dict = {}
                    for label in labels:
                        # Extract subkey from label: "category__metric__subkey" -> "subkey"
                        subkey = label.rsplit("__", 1)[-1]
                        sub_dict[subkey] = (
                            float(row_mapping[label])
                            if row_mapping[label] is not None
                            else 0.0
                        )
                    metrics_dict[user_key] = sub_dict
                else:
                    # PERCENTAGE/NUMERIC: flat float
                    label = labels[0]
                    metrics_dict[user_key] = (
                        float(row_mapping[label])
                        if row_mapping[label] is not None
                        else 0.0
                    )

            rows.append(
                AggregationRow(
                    group=group_dict,
                    population=float(population) if population is not None else 0.0,
                    density=float(density) if density is not None else None,
                    metrics=metrics_dict,
                )
            )

        return AggregationResponse(rows=rows, limit=self.limit, offset=self.offset, total_count=None)
