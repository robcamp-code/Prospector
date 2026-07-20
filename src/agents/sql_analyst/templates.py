"""SQL template strings for demographic queries."""

# Base CTE template with configurable geography grouping and filtering
BASE_CTE_TEMPLATE = """
WITH aggregated AS (
    SELECT
        {group_by_cols},
        SUM(population) AS population,
        SUM(
            CASE
                WHEN density IS NOT NULL AND density > 0
                THEN population / density
                ELSE 0
            END
        ) AS estimated_area_km2,
        {aggregation_expressions}
    FROM uszips
    WHERE {where_clause}
    GROUP BY {group_by_cols}
)
SELECT
    {select_cols},
    population,
    population / NULLIF(estimated_area_km2, 0) AS density,
    {final_expressions}
FROM aggregated
WHERE population > 0
{order_clause}
"""
