## Agent Design

### Use Case 1: Site Selection Report (Franchise Development)
query: I am franchise owner of Pink's Window Services based in Atlanta, Georgia. Pink's Window services is a home services franchise specializing in residential and commercial window cleaning along with related exterior cleaning services. Where within 1 hour of Atlanta should I open up the business?


1. User Persona Agent Builds a client_profile given this information. All of the fields in @./src/models/profiles.py need to be filled out.
This User Persona Agent needs to do 3 things:
 - Create an Ideal Customer for the business based on who historically buys this type of product or service
 - Find complimentary and competitor places API types
 - Write the ClientProfile to the DB


2. SQL Data Analyst Agent -- Scores each ZIP based on demographic alignment with the profile
 - Takes the ClientProfile and queries the DB for all relevant zips and does aggregate statistics across three categoryies:
 - state (largest)
 - cbsa_name
 - city
 - county
 - zip
From this it will rank the top 5 locations and give relevant metrics 

3. Based on output from SQL Data Analyst Agent, Generate a standalone HTML report.
