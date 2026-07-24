# ZIP Code Service Architecture

## Overview

The ZIP code service (`src/core/services/zips/`) provides geographic, demographic, and aggregation queries over US ZIP code census data. Previously a monolithic 400-line file, it's now organized as a modular package with clear responsibilities.

## Module Structure

### `utils.py` — Pure Utilities
Stateless helper functions:
- `nan_safe(col)` — Wraps columns to handle NaN sentinels (Postgres IEEE754 quirks)
- `get_group_field_name(col)` — Extract column key from SQLAlchemy attributes

**Use case**: Import when building custom queries or filters

```python
from src.core.services.zips.utils import nan_safe
```

### `filters.py` — Geographic Filters
`GeographicFilters` class encapsulates filter state and application:

```python
filters = GeographicFilters(
    state="New York",
    region="Northeast",
    county="Kings County",
    cbsa="New York-Newark-Jersey City",
    city=None,
)

# Apply to any SQLAlchemy select statement
stmt = select(USZip.zip, USZip.population)
stmt = filters.apply_to_statement(stmt)
```

**Extension**: Subclass or compose to add new filter types

### `metrics.py` — Metric Column Builder
`MetricColumnBuilder` class handles metric-type-aware column expression generation:

```python
builder = MetricColumnBuilder()

# Add numeric metric (median income)
builder.add_metric("income", "median_household_income")

# Add distribution metric (race breakdown: white, black, asian, etc.)
builder.add_metric("race", "distribution")

# Get all built column expressions
columns = builder.get_all_columns()  # dict[label, ColumnElement]
```

Handles three metric types:
- **DISTRIBUTION**: Multiple sub-keys (e.g., race components), each weighted by population
- **PERCENTAGE**: Single percentage value, weighted by population
- **NUMERIC**: Single numeric value, weighted by population

**Extension**: Extend to handle new metric types by modifying `add_metric()` logic

### `aggregation.py` — Query Builder & Orchestration
`AggregationQueryBuilder` class orchestrates the full aggregation pipeline:

```python
builder = AggregationQueryBuilder(
    session=db_session,
    group_by=GeographyLevel.STATE,
    metric_selectors=["income.median_household_income", "race.distribution"],
    sort_by="population",
    sort_dir="desc",
    limit=50,
    offset=0,
    state="California",  # Geographic filters passed as kwargs
    county=None,
)

# Build the statement (for inspection/testing)
stmt = builder.build_statement()

# Execute and get response
response = await builder.execute()  # Returns AggregationResponse
```

**Flow**:
1. Parse metric selectors (validate against DEMOGRAPHICS)
2. Build geographic filters
3. Build metric columns (via MetricColumnBuilder)
4. Compose SELECT/WHERE/GROUP BY/ORDER BY/LIMIT
5. Execute and transform results to AggregationResponse

### `geography.py` — Geographic Lookups
Pure functions for discovering distinct geographic values:

```python
states = await list_states(session)
counties = await list_counties(session, state="California")
cbsas = await list_cbsa_names(session, region="West Coast")
zips = await list_zips(session, county="Santa Clara County")
regions = get_region_list()  # No DB query needed
```

All functions use `GeographicFilters` internally for consistency.

### `demographics.py` — Demographics Discovery
Pure functions for discovering available metrics and categories:

```python
categories = get_demographic_categories()
# Returns list of (category_key, display_name, metric_keys)

metrics = get_demographic_metrics("income")
# Returns list of (metric_key, type, column_name)
```

### `__init__.py` — Public API
Clean exports via `__all__`:

```python
from src.core.services.zips import (
    # Entry point
    get_aggregation,
    
    # Geographic discovery
    list_cbsa_names,
    list_counties,
    list_zips,
    get_region_list,
    
    # Demographics discovery
    get_demographic_categories,
    get_demographic_metrics,
    
    # Builders (for extension/testing)
    AggregationQueryBuilder,
    GeographicFilters,
    MetricColumnBuilder,
)
```

## Backward Compatibility

**All public APIs unchanged**: Routes, schemas, and calling code require zero modifications.

```python
# Before and after — identical call signature
response = await get_aggregation(
    session=session,
    group_by=GeographyLevel.STATE,
    metric_selectors=["income.median_household_income"],
    state="California",
    sort_by="population",
)
```

## Extensibility Patterns

### Add a New Geographic Filter

```python
# In filters.py, extend GeographicFilters
class GeographicFilters:
    def __init__(self, ..., district: str | None = None):
        self.district = district
    
    def apply_to_statement(self, stmt):
        # ... existing code ...
        if self.district:
            stmt = stmt.where(USZip.congressional_district == self.district)
        return stmt
```

### Add a New Metric Type

```python
# In metrics.py, extend MetricColumnBuilder.add_metric()
elif metric.type == MetricType.CUSTOM:
    # Build custom column expression
    col = getattr(USZip, metric.column)
    label = f"{category}__{metric_key}"
    self.columns[label] = some_custom_aggregation_expr().label(label)
    labels.append(label)
```

### Use Builders Independently

```python
# Build filters without full aggregation
filters = GeographicFilters(state="New York")
stmt = select(USZip.zip, USZip.population).where(filters.apply_to_statement(...))

# Build metrics for a custom query
builder = MetricColumnBuilder()
builder.add_metric("income", "median_household_income")
my_columns = builder.get_all_columns()
```

## Testing

`tests/unit/test_zips_aggregation.py` includes:
- `test_aggregation_query_builder_composition()` — Builder state and statement building
- `test_metric_column_builder()` — Metric type handling
- `test_geographic_filters()` — Filter composition and application

Run with:
```bash
pytest tests/unit/test_zips_aggregation.py -v
```

## Performance Considerations

- **Query composition**: All SQL is built once and cached in the statement; no N+1 queries
- **NaN handling**: `nan_safe()` defers to Postgres; minimal Python overhead
- **Population weighting**: Done entirely in SQL aggregation functions
- **Metric parsing**: Validation happens upfront; expensive lookups cached in MetricColumnBuilder

## Future Improvements

- Query result caching for frequently-accessed aggregations
- Batch metric building (add_metrics() for multiple metrics in one pass)
- Custom aggregation strategies (e.g., median, percentile, mode)
- Geographic hierarchy navigation (drill-down from region → state → county → zip)
