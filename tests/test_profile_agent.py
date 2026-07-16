"""Tests for ProfileAgent."""

import pytest

from src.agents.profile_agent import ProfileAgent, VALID_PLACE_TYPES


@pytest.fixture
def agent():
    """Create a profile agent for testing."""
    return ProfileAgent()


@pytest.mark.skipif(
    not pytest.importorskip("openai", reason="OpenAI not available"),
    reason="Requires OpenAI API key",
)
class TestProfileAgentIntegration:
    """Integration tests requiring OpenAI API."""

    def test_gym_profile(self, agent):
        """Test getting types for a gym business."""
        types = agent.get_competitor_types(
            "budget gym targeting young professionals"
        )
        assert len(types) > 0
        assert any(t in types for t in ["gym", "fitness_center"])
        for t in types:
            assert t in VALID_PLACE_TYPES

    def test_restaurant_profile(self, agent):
        """Test getting types for a restaurant."""
        mapping = agent.get_place_types(
            "fast casual poke restaurant for health-conscious millennials"
        )
        assert len(mapping.competitor_types) > 0
        assert len(mapping.complementary_types) > 0
        # Should include restaurant-related types
        restaurant_types = ["restaurant", "fast_food_restaurant", "sushi_restaurant"]
        assert any(t in mapping.competitor_types for t in restaurant_types)

    def test_spa_profile(self, agent):
        """Test getting types for a spa business."""
        mapping = agent.get_place_types("luxury day spa for affluent women")
        assert "spa" in mapping.competitor_types or "beauty_salon" in mapping.competitor_types


class TestProfileAgentValidation:
    """Unit tests for type validation."""

    def test_valid_types_not_empty(self):
        """Ensure valid types list is populated."""
        assert len(VALID_PLACE_TYPES) > 50

    def test_common_types_included(self):
        """Check common place types are in the valid list."""
        common_types = [
            "gym",
            "restaurant",
            "coffee_shop",
            "spa",
            "bank",
            "hotel",
        ]
        for t in common_types:
            assert t in VALID_PLACE_TYPES
