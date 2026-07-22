"""State management for SQL Agent."""

from typing import TypedDict

from src.agents.orchestrator.demographics import CategoryName
from src.agents.sql_analyst.models import CategoryResult, SectionGrouping
from src.agents.sql_analyst.utils import GeographyLevel
from src.core.state import ClientProfileRef


class SQLAgentState(TypedDict):
    """State for SQL Agent report generation pipeline.

    This state tracks progress through the report generation process:
    1. Initialize with inputs (client_profile, geography filters)
    2. Process each demographic category -> category_results
    3. Group categories into sections -> section_groupings
    4. Build final report
    """

    # Input parameters
    client_profile: ClientProfileRef
    geography_level: GeographyLevel
    state_names: list[str] | None
    county_name: str | None
    region_name: str | None
    cbsa_names: list[str] | None

    # Processing state
    categories_to_process: list[CategoryName]
    category_results: list[CategoryResult]
    section_groupings: list[SectionGrouping]

    # Report configuration
    top_n_sections: int

    # Error tracking
    errors: list[str]
