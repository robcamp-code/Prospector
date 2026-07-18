## User Persona Redesign

This SQL Agent needs to generate a client Profile that has the client's ideal customer in terms of 
- Race
  - race_black
  - race_white
  - race_native
  - race_pacific
  - race_other
  - race_multiple
- Age
  - Columns: Should add up to 100%
    - age_under_10
    - age_10_to_19
    - age_20s
    - age_30s
    - age_40s
    - age_50s
    - age_60s
    - age_70s
    - age_over_80
  - Additional:
    - age_over_18
    - age_over_65

- Employment Status
- Marital Status
  - Columns: Should add to 100%
    - married
    - divorced
    - never_married
    - widowed
- Income: should add up to 100%
  - income_household_under_5: percentage of households with income less than $5K
  - income_household_5_to_10
  - income_household_10_to_15
  - income_household_15_to_20
  - income_household_20_to_25
  - income_household_25_to_35
  - income_household_35_to_50
  - income_household_50_to_75
  - income_household_75_to_100
  - income_household_100_to_150
  - income_household_150_over

- Educational Status: 
  - Columns: should add up to 100%
    - education_less_highschool
    - education_highschool
    - education_some_college
    - education_bachelors
    - education_graduate
  - Additional:
    - education_stem_degree


- Other:
  - rent_burden:	The median rent as a percentage of the median renter's household income
  - disabled: percentage of disabled folks.
  - veteran
  - farmer: The percentage of households reporting farm income on their 2016 IRS tax return.	
  - commute_time: The median commute time of resident workers in minutes.
  - charitable_givers: The percentage of households reporting charitable giving on their 2016 tax return. Note: Only filers who are itemizing will report charitable giving.
  - limited_english: The percentage of residents who only speak limited English.
  - health_uninsured:	The percentage of residents who report not having health insurance.

Given the customer's service description pick the top 5 demographics that are important to the customer and assign a weight of how important this demographic is to the customer, for example:

I am a spanish tutor who has successfully tutored over 1K students both on line and in person. I am trying to 
expand and open up a cultural immersion center where spanish and english speakers can share cultures and learn
a second language.


Example Query:
```
WITH county_stats AS (
    SELECT
        county_name,
        state_name,

        SUM(population) AS population,

        -- Calculate total area from ZIP population/density
        SUM(
            CASE 
                WHEN density IS NOT NULL AND density > 0 
                THEN population / density
                ELSE 0
            END
        ) AS estimated_area_km2,

        SUM(population * COALESCE(NULLIF(race_black, 'NaN'::float8), 0) / 100.0) AS black_population,
        SUM(population * COALESCE(NULLIF(race_white, 'NaN'::float8), 0) / 100.0) AS white_population,
        SUM(population * COALESCE(NULLIF(race_asian, 'NaN'::float8), 0) / 100.0) AS asian_population,
        SUM(population * COALESCE(NULLIF(race_native, 'NaN'::float8), 0) / 100.0) AS native_population,
        SUM(population * COALESCE(NULLIF(race_pacific, 'NaN'::float8), 0) / 100.0) AS pacific_population,
        SUM(population * COALESCE(NULLIF(race_other, 'NaN'::float8), 0) / 100.0) AS other_population,
        SUM(population * COALESCE(NULLIF(race_multiple, 'NaN'::float8), 0) / 100.0) AS multiple_population

    FROM uszips
    WHERE state_name = 'Georgia'
    GROUP BY county_name, state_name
)

SELECT
    county_name,
    state_name,

    population,

    -- Density per square kilometer
    population / NULLIF(estimated_area_km2, 0) AS density,

    black_population,
    white_population,
    asian_population,
    native_population,
    pacific_population,
    other_population,
    multiple_population,

    black_population    * 100.0 / population AS pct_black,
    white_population    * 100.0 / population AS pct_white,
    asian_population    * 100.0 / population AS pct_asian,
    native_population   * 100.0 / population AS pct_native,
    pacific_population  * 100.0 / population AS pct_pacific,
    other_population    * 100.0 / population AS pct_other,
    multiple_population * 100.0 / population AS pct_multiple

FROM county_stats
ORDER BY pct_black DESC;
```



