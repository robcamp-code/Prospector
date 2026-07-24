The SQL Agent's job is to generate a report object that will be used by a D3JS frontend. The report will provide useful visualizations that justify certain zip_codes, counties, cbsas, etc. The report is a pydantic model that can be held in state and a very useful visualization for the report is below:

Inside of @src/agents/orchestrator/demographics.py we have a DEMOGRAPHICS object that has all of the potential metrics we could use to rank a location.

The agent will iterate through 11 demographic categories and do the following:
1. Ask the LLM to extract the most useful query possible given the client preferences.
  - This LLM is equiped with the query tools defined in our unit tests

2. Rank How useful this data is to the user and use the importance_weight field.

3. Pick a visualization for this data and convert data to visualization response model

4. Group these visualizations into logical sections that make sense when writing a executive dashboard. Write a description of why you grouped these together and why this data is useful in the description field of the ReportSection pydantic model.

4. average the importance_weight of each visualization to get the importance weight for the section, and keep the top N sections.

At each step carefully think through:
- What pydantic models are required. Have we already defined a model of similar shape
- What should the system prompt be. 
- What tools are needed. See @./src/core/database or @src/core/region.
- Is an LLM needed at all at this step.

Finally, configure the router


## Coding standards
Log query results of all tool calls so I can have observability into query tool success rate.
Try to follow the same logical patterns in the @./src/agents/orchestrator package. Make improvements to the code quality as it was done quickly.

## Validation
Create a sample preferences and profile object of a fictitious business.
Create an integration test that allows me to run the analyst against the State Object with the fictitious company.
Create a just test-sql-agent.
Verify that a good report is successfully generated.
Inspect the report and make sure there are no alarming sections and the sections are of acceptable quality. If the quality of the sections are poor figure out what needs to be changed.
