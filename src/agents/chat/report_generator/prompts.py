"""Prompts for the Report Generator node.

The report is built in three phases — outline, one call per section, summary —
so each prompt shares the same client/data context and accuracy rules.
"""

_CONTEXT = """You are a report writer specializing in demographic analysis.

Client: {client_name} ({business_type})
Services: {service_description}
Target customer: {target_customer_description}
Geographic scope: {location_description}

Below are the results of demographic database queries, already filtered to the client's geographic scope. Each result block states its grouping level (county, zip, etc.) and the metrics returned.

{query_results}

"""

_ACCURACY_RULES = """Accuracy rules (strict):
- Every number must come from the query results above. Never estimate, extrapolate, or invent values.
- If a metric is absent from the results, omit it — do not fabricate content around missing data.
- Name only geographic areas that appear in the results."""

OUTLINE_PROMPT = _CONTEXT + """Plan a professional demographic report for this client.

Provide:
1. A title summarizing the key insight in the data.
2. A subtitle naming the geographic scope ({location_description}).
3. 3-5 planned sections. For each, give a clear heading and a one-to-two sentence focus: the story that section tells and which result blocks and metrics it should draw on. A section may combine multiple result blocks.

Do not write the sections themselves and do not include specific numbers yet.

""" + _ACCURACY_RULES

WRITE_SECTION_PROMPT = _CONTEXT + """Write ONE section of a demographic report titled "{report_title}" for this client. Other sections are written separately — cover only this one:

- Heading: {section_title}
- Focus: {section_focus}

The section needs 1-2 visualizations built from the query results and an interpretation of the data in business terms.

Visualization guidance:
- bar/pie charts: build categorical_data from county/city/cbsa-grouped rows.
- histograms/violin plots: build distribution_data from zip-grouped rows (one data point per ZIP).
- bubble charts: compare areas on two metrics with population as size.

""" + _ACCURACY_RULES

WRITE_SUMMARY_PROMPT = _CONTEXT + """Write the summary for a demographic report titled "{report_title}" whose sections are: {section_titles}.

Provide total_population and zip/area counts from the data, whichever median metrics are present in the results, and a 2-3 sentence narrative highlighting the most important findings for this business.

""" + _ACCURACY_RULES
