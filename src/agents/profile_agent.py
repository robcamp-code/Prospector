"""Langchain agent for converting client profiles to Places API types."""

import json
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

load_dotenv()


@dataclass
class PlaceTypeMapping:
    """Mapping of place types for a business profile."""

    competitor_types: list[str]
    complementary_types: list[str]


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

SYSTEM_PROMPT = """You are an expert at understanding business profiles and identifying relevant Google Places API types.

Given a business description, identify:
1. COMPETITOR_TYPES: Place types that are direct competitors or similar businesses
2. COMPLEMENTARY_TYPES: Place types that attract similar customers but are not competitors

You must ONLY use place types from this valid list:
{valid_types}

Respond with a JSON object containing two arrays:
- competitor_types: array of place type strings for competitors
- complementary_types: array of place type strings for complementary businesses

Return 3-7 types for each category. Be specific and relevant to the business described.

Example for "budget gym targeting young professionals":
{{
    "competitor_types": ["gym", "fitness_center", "yoga_studio", "pilates_studio"],
    "complementary_types": ["coffee_shop", "juice_shop", "sporting_goods_store", "corporate_office"]
}}

Example for "upscale Italian restaurant":
{{
    "competitor_types": ["italian_restaurant", "restaurant", "steak_house", "mediterranean_restaurant"],
    "complementary_types": ["bar", "movie_theater", "spa", "jewelry_store", "art_gallery"]
}}

Respond with ONLY the JSON object, no other text."""


class ProfileAgent:
    """Agent for converting user business profiles to Places API types."""

    def __init__(self, model: str = "gpt-4o-mini"):
        """Initialize the profile agent.

        Args:
            model: OpenAI model to use (default: gpt-4o-mini for cost efficiency)
        """
        self.llm = ChatOpenAI(model=model, temperature=0)

    def get_place_types(self, service_description: str) -> PlaceTypeMapping:
        """Convert a business service description to Places API types.

        Args:
            service_description: Natural language description of the business
                (e.g., "fast casual poke restaurant for health-conscious millennials")

        Returns:
            PlaceTypeMapping with competitor and complementary types
        """
        messages = [
            SystemMessage(
                content=SYSTEM_PROMPT.format(valid_types=", ".join(VALID_PLACE_TYPES))
            ),
            HumanMessage(content=service_description),
        ]

        response = self.llm.invoke(messages)

        # Parse JSON response
        try:
            content = response.content.strip()
            # Handle potential markdown code blocks
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            data = json.loads(content)
        except json.JSONDecodeError:
            # Fallback to default types if parsing fails
            return PlaceTypeMapping(
                competitor_types=["restaurant"],
                complementary_types=["coffee_shop"],
            )

        # Validate types against allowed list
        competitor_types = [
            t for t in data.get("competitor_types", []) if t in VALID_PLACE_TYPES
        ]
        complementary_types = [
            t for t in data.get("complementary_types", []) if t in VALID_PLACE_TYPES
        ]

        return PlaceTypeMapping(
            competitor_types=competitor_types or ["restaurant"],
            complementary_types=complementary_types or ["coffee_shop"],
        )

    def get_competitor_types(self, service_description: str) -> list[str]:
        """Get competitor place types for a business.

        Args:
            service_description: Natural language description of the business

        Returns:
            List of competitor place type strings
        """
        mapping = self.get_place_types(service_description)
        return mapping.competitor_types

    def get_complementary_types(self, service_description: str) -> list[str]:
        """Get complementary place types for a business.

        Args:
            service_description: Natural language description of the business

        Returns:
            List of complementary place type strings
        """
        mapping = self.get_place_types(service_description)
        return mapping.complementary_types
