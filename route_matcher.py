"""Route matching and deduplication cache for TransitPulse alerts."""

import logging
import time

logger = logging.getLogger(__name__)

USER_ROUTE_ZONES: set[str] = {
    "Silk Board Junction",
    "Koramangala",
    "HSR Layout",
    "BTM Layout",
    "Electronic City",
}

DEDUP_COOLDOWN_SECONDS: int = 45

# In-memory dedup cache: maps "Zone:Category" → last-alerted Unix timestamp
_dedup_cache: dict[str, float] = {}


def is_on_route(zone: str) -> bool:
    """Check whether a zone falls on the user's active commute route."""
    return zone in USER_ROUTE_ZONES


def _cache_key(zone: str, category: str) -> str:
    """Build a deterministic cache key from zone and category."""
    return f"{zone}:{category}"


def is_duplicate(zone: str, category: str) -> bool:
    """Return True if the same zone+category was alerted within the cooldown window."""
    key = _cache_key(zone, category)
    last_ts = _dedup_cache.get(key)
    if last_ts is None:
        return False
    elapsed = time.time() - last_ts
    if elapsed < DEDUP_COOLDOWN_SECONDS:
        logger.info("Dedup suppressed: %s (%.0fs remaining)", key, DEDUP_COOLDOWN_SECONDS - elapsed)
        return True
    return False


def mark_alerted(zone: str, category: str) -> None:
    """Record the current time for a zone+category alert."""
    key = _cache_key(zone, category)
    _dedup_cache[key] = time.time()
    logger.info("Dedup cache updated: %s", key)


def get_route_zones() -> list[str]:
    """Return the user's route zones as a sorted list."""
    return sorted(USER_ROUTE_ZONES)


def clear_dedup_cache() -> None:
    """Clear the deduplication cache (useful for testing)."""
    _dedup_cache.clear()
