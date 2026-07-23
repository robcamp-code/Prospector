"""Metric column building for ZIP aggregations."""

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.sql import ColumnElement

from src.core.database import USZip
from src.core.demographics import DEMOGRAPHICS, MetricType
from src.core.services.zips.utils import nan_safe


class MetricColumnBuilder:
    """Builds labeled column expressions for metrics (DISTRIBUTION, PERCENTAGE, NUMERIC)."""

    def __init__(self):
        self.columns: dict[str, ColumnElement] = {}
        self.metric_to_labels: dict[tuple[str, str], list[str]] = {}

    def add_metric(self, category: str, metric_key: str) -> list[str]:
        """Add a metric, building its column(s). Returns list of SQL labels."""
        # Validate
        if category not in DEMOGRAPHICS.categories:
            raise HTTPException(
                status_code=400, detail=f"Unknown category '{category}'"
            )
        if metric_key not in DEMOGRAPHICS.get_category(category).metrics:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown metric '{metric_key}' in category '{category}'",
            )

        metric = DEMOGRAPHICS.get_metric(category, metric_key)
        pop = USZip.population
        labels = []

        if metric.type == MetricType.DISTRIBUTION:
            for subkey, col_name in metric.columns.items():
                col = getattr(USZip, col_name)
                label = f"{category}__{metric_key}__{subkey}"
                # Weighted population percentage: SUM(population * pct/100) * 100 / SUM(population)
                self.columns[label] = (
                    func.sum(nan_safe(pop) * nan_safe(col) / 100.0) * 100.0
                    / func.sum(nan_safe(pop))
                ).label(label)
                labels.append(label)

        elif metric.type == MetricType.PERCENTAGE:
            col = getattr(USZip, metric.column)
            label = f"{category}__{metric_key}"
            self.columns[label] = (
                func.sum(nan_safe(pop) * nan_safe(col) / 100.0) * 100.0
                / func.sum(nan_safe(pop))
            ).label(label)
            labels.append(label)

        elif metric.type == MetricType.NUMERIC:
            col = getattr(USZip, metric.column)
            label = f"{category}__{metric_key}"
            self.columns[label] = (
                func.sum(nan_safe(pop) * nan_safe(col))
                / func.nullif(func.sum(nan_safe(pop)), 0)
            ).label(label)
            labels.append(label)

        self.metric_to_labels[(category, metric_key)] = labels
        return labels

    def get_all_columns(self) -> dict[str, ColumnElement]:
        """Return all built metric columns."""
        return self.columns

    def get_metric_labels(self, category: str, metric_key: str) -> list[str]:
        """Get labels for a specific metric."""
        return self.metric_to_labels.get((category, metric_key), [])
