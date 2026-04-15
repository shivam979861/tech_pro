"""Tests for route matching and deduplication cache."""

from unittest.mock import patch

import pytest

from route_matcher import (
    USER_ROUTE_ZONES,
    _dedup_cache,
    clear_dedup_cache,
    is_duplicate,
    is_on_route,
    mark_alerted,
    get_route_zones,
)


@pytest.fixture(autouse=True)
def _clean_cache():
    """Ensure a clean dedup cache for every test."""
    clear_dedup_cache()
    yield
    clear_dedup_cache()


# ── Route matching ────────────────────────────────────────────────────
class TestRouteMatching:
    def test_known_zone_on_route(self) -> None:
        assert is_on_route("Silk Board Junction") is True

    def test_unknown_zone_off_route(self) -> None:
        assert is_on_route("Whitefield") is False

    def test_all_route_zones_match(self) -> None:
        for zone in USER_ROUTE_ZONES:
            assert is_on_route(zone) is True

    def test_get_route_zones_returns_sorted_list(self) -> None:
        zones = get_route_zones()
        assert isinstance(zones, list)
        assert zones == sorted(zones)
        assert len(zones) == 5


# ── Deduplication cache ───────────────────────────────────────────────
class TestDedupCache:
    def test_first_call_not_duplicate(self) -> None:
        assert is_duplicate("Silk Board Junction", "Flood") is False

    def test_second_call_within_cooldown_is_duplicate(self) -> None:
        mark_alerted("Silk Board Junction", "Flood")
        assert is_duplicate("Silk Board Junction", "Flood") is True

    def test_different_category_not_duplicate(self) -> None:
        mark_alerted("Silk Board Junction", "Flood")
        assert is_duplicate("Silk Board Junction", "Accident") is False

    def test_different_zone_not_duplicate(self) -> None:
        mark_alerted("Silk Board Junction", "Flood")
        assert is_duplicate("Koramangala", "Flood") is False

    def test_cache_expires_after_cooldown(self) -> None:
        """After cooldown period, the same zone+category should no longer be duplicate."""
        mark_alerted("HSR Layout", "Obstruction")
        assert is_duplicate("HSR Layout", "Obstruction") is True

        # Simulate time passing beyond the cooldown
        from route_matcher import DEDUP_COOLDOWN_SECONDS
        with patch("route_matcher.time.time", return_value=_dedup_cache["HSR Layout:Obstruction"] + DEDUP_COOLDOWN_SECONDS + 1):
            assert is_duplicate("HSR Layout", "Obstruction") is False

    def test_clear_cache(self) -> None:
        mark_alerted("BTM Layout", "HazMat")
        assert is_duplicate("BTM Layout", "HazMat") is True
        clear_dedup_cache()
        assert is_duplicate("BTM Layout", "HazMat") is False
