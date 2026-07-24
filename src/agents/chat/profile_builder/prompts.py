"""Prompts for the Profile Builder node."""

DISCOVERY_PROMPT = """
You are a business analyst gathering information about a client's business and target market.

Extract the client's preferences from the conversation below into the structured schema. Fill in as many fields as possible from what the client has said; leave fields null (or empty lists) if not mentioned.

Field guidance:
- name: the business name.
- business_type: e.g. retail, fitness, hospitality, professional services, tutoring.
- service_description: what they sell or offer.
- price_point: budget, mid-range, premium, or a stated price (e.g. "$75/session").
- target_customer_description: who their ideal customer is, in their words.
- location: where they want to operate. This describes WHERE to look, never how to group results.
  - region: EXACTLY one of east_coast, west_coast, midwest, south, mountain_west (map phrases: "the East Coast" or "the Northeast" -> east_coast; "out west" -> west_coast or mountain_west; "the South" -> south). Null if they named specific states instead.
  - states: full state names (e.g. "Georgia"), only if the client named them.
  - area_type: "urban" only if they say urban/city/metro areas, "suburban" for suburbs, "rural" for rural/country, otherwise "any".
- demographic_categories: which demographic dimensions matter to their targeting, chosen from: race, age, employment, marital_status, income, education, housing, health, community, language, transportation. (e.g. "college-educated" -> education; "bilingual/Spanish-speaking" -> language and race; "wealthy families" -> income and marital_status.)

Current conversation:
{conversation}"""
