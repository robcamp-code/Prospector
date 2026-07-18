"""Output models for the SQL Analyst Agent."""

from pydantic import BaseModel, Field


class RankedLocation(BaseModel):
    """A ranked geographic location with demographic metrics."""

    rank: int = Field(description="Ranking position (1 = best)")
    geo_type: str = Field(description="Geographic level: state, cbsa, county, city, or zip")
    name: str = Field(description="Name of the geographic area")
    score: float = Field(description="Profile match score (0-100)")
    population: float = Field(description="Total population")
    median_income: float = Field(description="Population-weighted median household income")
    median_age: float = Field(description="Population-weighted median age")
    home_ownership: float = Field(description="Population-weighted home ownership rate")
    education_rate: float = Field(description="Population-weighted college education rate")
    zip_count: int = Field(description="Number of ZIP codes in this area")
    zip_codes: list[str] = Field(
        default_factory=list,
        description="List of ZIP codes (only populated for city/zip level)",
    )


class AnalysisResult(BaseModel):
    """Complete analysis output from SQL Analyst Agent."""

    profile_id: int = Field(description="ID of the ClientProfile used for analysis")
    profile_name: str = Field(description="Name of the ClientProfile")
    target_geography: str = Field(description="The geography analyzed (e.g., CBSA name or state)")
    geography_type: str = Field(description="Type of geography: 'cbsa' or 'state'")

    # Hierarchical rankings (top 5 at each level)
    top_states: list[RankedLocation] = Field(
        default_factory=list,
        description="Top 5 ranked states (only when analyzing multiple states)",
    )
    top_cbsas: list[RankedLocation] = Field(
        default_factory=list,
        description="Top 5 ranked CBSA metro areas",
    )
    top_counties: list[RankedLocation] = Field(
        default_factory=list,
        description="Top 5 ranked counties",
    )
    top_cities: list[RankedLocation] = Field(
        default_factory=list,
        description="Top 5 ranked cities",
    )
    top_zips: list[RankedLocation] = Field(
        default_factory=list,
        description="Top 5 ranked ZIP codes",
    )

    # Summary statistics
    total_zips_analyzed: int = Field(description="Total number of ZIP codes analyzed")
    total_population: float = Field(description="Total population across all ZIPs")
