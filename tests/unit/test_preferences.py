"""Tests for the typed Preferences schema and its safe-loading helper."""

import pytest
from pydantic import ValidationError

from src.core.urbanicity import SUBURBAN_MIN_DENSITY, URBAN_MIN_DENSITY, density_bounds
from src.schemas.preferences import (
    LocationPreference,
    Preferences,
    load_preferences,
)


def _complete_preferences(**overrides) -> Preferences:
    base = dict(
        name="Cultura+",
        business_type="tutoring",
        service_description="Bilingual tutoring and cultural immersion",
        price_point="$75/session",
        target_customer_description="College-educated bilingual families",
        location=LocationPreference(region="east_coast", area_type="urban"),
        demographic_categories=["education", "income", "race"],
    )
    base.update(overrides)
    return Preferences(**base)


class TestLocationPreference:
    def test_rejects_unknown_region(self):
        with pytest.raises(ValidationError):
            LocationPreference(region="East Coast")  # only canonical keys allowed

    def test_accepts_canonical_region(self):
        loc = LocationPreference(region="east_coast")
        assert loc.region == "east_coast"

    def test_drops_unknown_states_silently(self):
        loc = LocationPreference(states=["Georgia", "Atlantis"])
        assert loc.states == ["Georgia"]

    def test_nationwide_when_empty(self):
        assert LocationPreference().is_nationwide()
        assert not LocationPreference(states=["Georgia"]).is_nationwide()

    def test_filter_kwargs_urban_region(self):
        loc = LocationPreference(region="east_coast", area_type="urban")
        kwargs = loc.filter_kwargs()
        assert kwargs["region"] == "east_coast"
        assert kwargs["min_density"] == URBAN_MIN_DENSITY
        assert kwargs["max_density"] is None
        assert kwargs["states"] is None

    def test_filter_kwargs_rural_states(self):
        loc = LocationPreference(states=["Georgia"], area_type="rural")
        kwargs = loc.filter_kwargs()
        assert kwargs["states"] == ["Georgia"]
        assert kwargs["min_density"] is None
        assert kwargs["max_density"] == SUBURBAN_MIN_DENSITY

    def test_describe(self):
        loc = LocationPreference(region="east_coast", area_type="urban")
        assert "east_coast" in loc.describe()
        assert "urban" in loc.describe()
        assert LocationPreference().describe() == "nationwide"


class TestDensityBounds:
    def test_all_area_types(self):
        assert density_bounds("urban") == (URBAN_MIN_DENSITY, None)
        assert density_bounds("suburban") == (SUBURBAN_MIN_DENSITY, URBAN_MIN_DENSITY)
        assert density_bounds("rural") == (None, SUBURBAN_MIN_DENSITY)
        assert density_bounds("any") == (None, None)

    def test_unknown_area_type_is_unbounded(self):
        assert density_bounds("weird") == (None, None)


class TestPreferences:
    def test_complete(self):
        prefs = _complete_preferences()
        assert prefs.is_complete()
        assert prefs.missing_fields() == []

    def test_missing_fields(self):
        prefs = _complete_preferences(price_point=None, location=None)
        assert not prefs.is_complete()
        assert set(prefs.missing_fields()) == {"price_point", "location"}

    def test_whitespace_is_missing(self):
        prefs = _complete_preferences(name="   ")
        assert "name" in prefs.missing_fields()

    def test_rejects_unknown_category(self):
        with pytest.raises(ValidationError):
            _complete_preferences(demographic_categories=["astrology"])

    def test_merge_missing_from(self):
        old = _complete_preferences()
        new = Preferences(name="Cultura+ Rebrand")
        merged = new.merge_missing_from(old)
        assert merged.name == "Cultura+ Rebrand"  # new value wins
        assert merged.business_type == "tutoring"  # gap filled from old
        assert merged.location.region == "east_coast"
        assert merged.is_complete()


class TestLoadPreferences:
    def test_roundtrip(self):
        prefs = _complete_preferences()
        loaded = load_preferences(prefs.model_dump())
        assert loaded == prefs

    def test_none_and_non_dict(self):
        assert load_preferences(None) is None
        assert load_preferences("garbage") is None

    def test_legacy_or_corrupt_dict_returns_none(self):
        # Legacy shape (e.g. old free-text location) must not crash a resumed
        # conversation — it deserializes as incomplete-but-valid or None.
        corrupt = {"location": {"region": "East Coast"}}  # invalid region casing
        assert load_preferences(corrupt) is None

    def test_partial_dict_loads_as_incomplete(self):
        loaded = load_preferences({"name": "Cultura+"})
        assert loaded is not None
        assert not loaded.is_complete()
