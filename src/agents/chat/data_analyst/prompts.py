"""Prompts for Data Analyst node."""

LOCATION_EXTRACTION_PROMPT = """You are a geography expert. Extract and normalize location information from the client's stated preferences.

Determine:
1. Scope: "nationwide" (entire US), "region" (e.g., South, Midwest), "states" (specific states), or "metros" (metro areas)
2. Region name: if applicable (e.g., "South", "Northeast", "West Coast")
3. State names: list of states, if mentioned
4. CBSA names: metro area names, if mentioned
5. Area type: "urban", "suburban", "rural", or "any"

Provide reasoning for your interpretation.

Client's raw location preference: "{location_preference}"

Extract the location filters from this preference."""
