"""Service for Google Places API integration with caching."""

from collections import Counter
from datetime import datetime, timedelta

from google.auth import default
from google.maps import places_v1
from google.type.latlng_pb2 import LatLng
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.v0.models.places import Place
from src.v0.utils.address import parse_address


# Places API field mask for search requests
PLACES_FIELD_MASK = ",".join([
    "places.id",
    "places.name",
    "places.displayName",
    "places.types",
    "places.primaryType",
    "places.nationalPhoneNumber",
    "places.websiteUri",
    "places.formattedAddress",
    "places.location",
    "places.rating",
    "places.userRatingCount",
])

# Place type categories for business analysis
PLACE_TYPE_CATEGORIES = {
    "fitness": [
        "gym",
        "fitness_center",
        "yoga_studio",
        "pilates_studio",
        "sports_club",
    ],
    "food_qsr": [
        "fast_food_restaurant",
        "meal_takeaway",
        "sandwich_shop",
        "pizza_restaurant",
    ],
    "food_casual": ["restaurant", "cafe", "coffee_shop", "bar", "bakery"],
    "medical": [
        "doctor",
        "dentist",
        "dental_clinic",
        "medical_lab",
        "pharmacy",
        "hospital",
    ],
    "retail": [
        "shopping_mall",
        "department_store",
        "clothing_store",
        "shoe_store",
    ],
    "services": [
        "bank",
        "insurance_agency",
        "real_estate_agency",
        "accounting",
        "lawyer",
    ],
    "automotive": ["car_dealer", "car_repair", "car_wash", "gas_station"],
    "personal_care": ["hair_salon", "beauty_salon", "spa", "barber_shop"],
}

# Cache expiration time
CACHE_EXPIRY_HOURS = 24


class PlacesService:
    """Service for querying Google Places API with local caching."""

    def __init__(self, db: Session):
        self.db = db
        credentials, _ = default()
        self.client = places_v1.PlacesClient(credentials=credentials)

    def _cache_place(self, place: places_v1.Place) -> Place:
        """Cache a Places API response to the database.

        Args:
            place: Google Places API Place object

        Returns:
            Cached Place database object
        """
        # Parse address for zip code
        address = place.formatted_address or ""
        parsed = parse_address(address)

        # Check if already cached
        existing = self.db.execute(
            select(Place).where(Place.place_id == place.id)
        ).scalar_one_or_none()

        if existing:
            # Update existing cache entry
            existing.name = place.name
            existing.display_name = (
                place.display_name.text if place.display_name else None
            )
            existing.primary_type = place.primary_type or None
            existing.types = list(place.types) if place.types else None
            existing.lat = place.location.latitude if place.location else None
            existing.lng = place.location.longitude if place.location else None
            existing.zip_code = parsed.zip_code
            existing.address = address
            existing.phone = place.national_phone_number or None
            existing.website = place.website_uri or None
            existing.rating = place.rating or None
            existing.review_count = place.user_rating_count or None
            existing.cached_at = datetime.utcnow()
            self.db.commit()
            return existing

        # Create new cache entry
        db_place = Place(
            place_id=place.id,
            name=place.name,
            display_name=place.display_name.text if place.display_name else None,
            primary_type=place.primary_type or None,
            types=list(place.types) if place.types else None,
            lat=place.location.latitude if place.location else None,
            lng=place.location.longitude if place.location else None,
            zip_code=parsed.zip_code,
            address=address,
            phone=place.national_phone_number or None,
            website=place.website_uri or None,
            rating=place.rating or None,
            review_count=place.user_rating_count or None,
        )
        self.db.add(db_place)
        self.db.commit()
        return db_place

    def _get_cached_nearby(
        self,
        lat: float,
        lng: float,
        types: list[str],
        radius_m: int,
    ) -> list[Place] | None:
        """Check cache for recent nearby search results.

        Returns None if cache is stale or missing.
        """
        # Simple cache check - find places of matching types in approximate area
        # This is a simplified approach; production would use spatial indexing
        cache_cutoff = datetime.utcnow() - timedelta(hours=CACHE_EXPIRY_HOURS)

        lat_delta = radius_m / 111000
        lng_delta = radius_m / 111000

        stmt = select(Place).where(
            Place.cached_at >= cache_cutoff,
            Place.lat >= lat - lat_delta,
            Place.lat <= lat + lat_delta,
            Place.lng >= lng - lng_delta,
            Place.lng <= lng + lng_delta,
        )

        cached = self.db.execute(stmt).scalars().all()

        # Filter by type if we have cached results
        if cached and types:
            filtered = [
                p for p in cached
                if p.primary_type in types
                or (p.types and any(t in types for t in p.types))
            ]
            if filtered:
                return filtered

        return None

    def search_nearby(
        self,
        lat: float,
        lng: float,
        types: list[str],
        radius_m: int = 5000,
        max_results: int = 20,
        use_cache: bool = True,
    ) -> list[Place]:
        """Search for places near a location.

        Args:
            lat: Center latitude
            lng: Center longitude
            types: List of place types to search for
            radius_m: Search radius in meters
            max_results: Maximum results to return
            use_cache: Whether to use cached results

        Returns:
            List of Place objects
        """
        # Check cache first
        if use_cache:
            cached = self._get_cached_nearby(lat, lng, types, radius_m)
            if cached:
                return cached[:max_results]

        # Query Places API
        request = places_v1.SearchNearbyRequest(
            location_restriction=places_v1.SearchNearbyRequest.LocationRestriction(
                circle=places_v1.Circle(
                    center=LatLng(latitude=lat, longitude=lng),
                    radius=radius_m,
                )
            ),
            included_types=types,
            language_code="en",
            max_result_count=max_results,
        )

        response = self.client.search_nearby(
            request=request,
            metadata=[("x-goog-fieldmask", PLACES_FIELD_MASK)],
        )

        # Cache results
        results = []
        for place in response.places:
            cached = self._cache_place(place)
            results.append(cached)

        return results

    def count_by_type(
        self,
        lat: float,
        lng: float,
        radius_m: int,
        place_type: str,
    ) -> int:
        """Count places of a specific type within a radius.

        Args:
            lat: Center latitude
            lng: Center longitude
            radius_m: Search radius in meters
            place_type: Place type to count

        Returns:
            Count of places
        """
        places = self.search_nearby(lat, lng, [place_type], radius_m, max_results=20)
        return len(places)

    def get_business_mix(
        self,
        lat: float,
        lng: float,
        radius_m: int = 5000,
    ) -> dict[str, int]:
        """Get breakdown of business categories in an area.

        Args:
            lat: Center latitude
            lng: Center longitude
            radius_m: Search radius in meters

        Returns:
            Dict mapping category names to counts
        """
        category_counts: dict[str, int] = {}

        for category, types in PLACE_TYPE_CATEGORIES.items():
            places = self.search_nearby(lat, lng, types, radius_m, max_results=20)
            category_counts[category] = len(places)

        return category_counts

    def get_competitors(
        self,
        lat: float,
        lng: float,
        competitor_types: list[str],
        radius_m: int = 5000,
    ) -> list[Place]:
        """Get competitor businesses near a location.

        Args:
            lat: Center latitude
            lng: Center longitude
            competitor_types: List of place types considered competitors
            radius_m: Search radius in meters

        Returns:
            List of competitor Place objects
        """
        return self.search_nearby(lat, lng, competitor_types, radius_m, max_results=20)

    def get_complementary(
        self,
        lat: float,
        lng: float,
        complementary_types: list[str],
        radius_m: int = 5000,
    ) -> list[Place]:
        """Get complementary businesses near a location.

        Args:
            lat: Center latitude
            lng: Center longitude
            complementary_types: List of place types considered complementary
            radius_m: Search radius in meters

        Returns:
            List of complementary Place objects
        """
        return self.search_nearby(
            lat, lng, complementary_types, radius_m, max_results=20
        )
