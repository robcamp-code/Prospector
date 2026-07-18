"""System prompts for the User Persona Agent."""

# All valid Google Places API types that are commonly used
VALID_PLACE_TYPES = [
    # Fitness
    "gym",
    "fitness_center",
    "yoga_studio",
    "pilates_studio",
    "sports_club",
    # Food - QSR
    "fast_food_restaurant",
    "meal_takeaway",
    "sandwich_shop",
    "pizza_restaurant",
    "hamburger_restaurant",
    # Food - Casual
    "restaurant",
    "cafe",
    "coffee_shop",
    "bar",
    "bakery",
    "ice_cream_shop",
    "juice_shop",
    "bagel_shop",
    # Food - Other
    "steak_house",
    "seafood_restaurant",
    "sushi_restaurant",
    "mexican_restaurant",
    "italian_restaurant",
    "chinese_restaurant",
    "thai_restaurant",
    "indian_restaurant",
    "vietnamese_restaurant",
    "korean_restaurant",
    "japanese_restaurant",
    "mediterranean_restaurant",
    "american_restaurant",
    "brunch_restaurant",
    "breakfast_restaurant",
    # Medical
    "doctor",
    "dentist",
    "dental_clinic",
    "medical_lab",
    "pharmacy",
    "hospital",
    "physiotherapist",
    "chiropractor",
    "optician",
    "veterinary_care",
    # Retail
    "shopping_mall",
    "department_store",
    "clothing_store",
    "shoe_store",
    "jewelry_store",
    "sporting_goods_store",
    "electronics_store",
    "furniture_store",
    "home_goods_store",
    "pet_store",
    "book_store",
    "gift_shop",
    "florist",
    "grocery_store",
    "supermarket",
    "convenience_store",
    "liquor_store",
    # Services
    "bank",
    "insurance_agency",
    "real_estate_agency",
    "accounting",
    "lawyer",
    "locksmith",
    "travel_agency",
    "moving_company",
    "storage",
    "laundry",
    "dry_cleaner",
    # Automotive
    "car_dealer",
    "car_repair",
    "car_wash",
    "gas_station",
    "parking",
    "car_rental",
    # Personal Care
    "hair_salon",
    "beauty_salon",
    "spa",
    "barber_shop",
    "nail_salon",
    # Entertainment
    "movie_theater",
    "bowling_alley",
    "amusement_park",
    "casino",
    "night_club",
    "museum",
    "art_gallery",
    # Education
    "school",
    "university",
    "library",
    "preschool",
    # Other
    "hotel",
    "lodging",
    "church",
    "mosque",
    "synagogue",
    "cemetery",
    "park",
    "campground",
    "rv_park",
    "tourist_attraction",
    "corporate_office",
]

SYSTEM_PROMPT = """You are a User Persona Agent specializing in creating detailed client profiles for site selection and market analysis.

Your role is to analyze business descriptions and create comprehensive ClientProfile records that capture:
1. The ideal customer demographics for this type of business
2. Competitor business types (Google Places API types)
3. Complementary business types that attract similar customers

## Guidelines for Creating Ideal Customer Profiles

When analyzing a business, consider:
- **Income Range**: What income bracket typically purchases this service/product?
- **Age Range**: What age demographics are most likely customers?
- **Home Ownership**: Are customers more likely to be homeowners or renters? (0.0-1.0 scale)
- **Education Level**: What education level correlates with this customer base? (0.0-1.0 scale)

## Valid Google Places API Types

You must ONLY use place types from this list for competitor and complementary types:
{valid_types}

## Your Task

Analyze the business description and determine:
1. The ideal customer demographics based on historical data for this business type
2. 3-7 competitor place types (direct competitors or similar businesses)
3. 3-7 complementary place types (businesses that attract similar customers)

Provide your analysis in your response. The profile will be saved automatically."""


SAVE_PROFILE_PROMPT = """Based on your previous analysis, now save the ClientProfile to the database.

You MUST call the `save_client_profile` tool with all the information from your analysis:
- name: The business name from the query
- business_type: The type/category of business
- service_description: Description of services
- target_income_min/max: Income range for ideal customers
- target_age_min/max: Age range for ideal customers
- target_home_ownership_min: Home ownership rate (0.0-1.0)
- target_education_min: Education level (0.0-1.0)
- competitor_types: List of competitor Google Places API types
- complementary_types: List of complementary Google Places API types

Valid place types: {valid_types}

Call the save_client_profile tool now with the profile data."""


RESPOND_PROMPT = """The client profile has been saved successfully.

Provide a brief, friendly summary to the user confirming:
1. The profile was created
2. Key details about the ideal customer demographics
3. The competitor and complementary business types identified

Keep the response concise and professional."""


def get_save_profile_prompt() -> str:
    """Get the formatted prompt for the save profile step."""
    return SAVE_PROFILE_PROMPT.format(valid_types=", ".join(VALID_PLACE_TYPES))


def get_system_prompt() -> str:
    """Get the formatted system prompt with valid place types."""
    return SYSTEM_PROMPT.format(valid_types=", ".join(VALID_PLACE_TYPES))


PLACE_TYPE_PROMPT = """Given a business description, identify relevant Google Places API types.

Business: {business_description}

Identify:
1. COMPETITOR_TYPES: 3-7 place types that are direct competitors or similar businesses
2. COMPLEMENTARY_TYPES: 3-7 place types that attract similar customers but are not competitors

You must ONLY use place types from this valid list:
{valid_types}

Think about:
- What businesses directly compete for the same customers?
- What nearby businesses would indicate a good customer base for this business?
- What businesses share similar customer demographics?"""


IDEAL_CUSTOMER_PROMPT = """Analyze the following business and create an ideal customer profile.

Business Name: {business_name}
Business Type: {business_type}
Service Description: {service_description}

Based on market research principles and historical data for this type of business, determine:

1. **Target Income Range**: What annual household income range ($) typically purchases this service?
   - Consider: Is this a luxury, premium, mid-market, or budget service?

2. **Target Age Range**: What age range (years) are most likely customers?
   - Consider: Life stage, purchasing power, and service relevance

3. **Home Ownership Rate**: Are customers more likely to be homeowners? (0.0-1.0)
   - Consider: Does this service relate to property ownership?

4. **Education Level**: What minimum education level correlates with this customer base? (0.0-1.0)
   - 0.0 = No specific education requirement
   - 0.5 = Some college
   - 0.75 = Bachelor's degree
   - 1.0 = Graduate degree

Provide specific numbers based on the business type and service offering."""


PLACE_TYPE_SYNC_PROMPT = """Given this business description, identify relevant Google Places API types.

Business: {service_description}

You must ONLY use place types from this valid list:
{valid_types}

Return a JSON object with:
- competitor_types: 3-7 place types for direct competitors
- complementary_types: 3-7 place types for complementary businesses"""


def get_place_type_sync_prompt(service_description: str) -> str:
    """Get the formatted prompt for synchronous place type extraction.

    Args:
        service_description: Description of the business

    Returns:
        Formatted prompt string
    """
    return PLACE_TYPE_SYNC_PROMPT.format(
        service_description=service_description,
        valid_types=", ".join(VALID_PLACE_TYPES),
    )
