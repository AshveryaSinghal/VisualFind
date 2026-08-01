"""
Generic TTL cache backed by the search_cache SQLite table.

Two things get cached here:
  1. Full search results keyed by the uploaded image's sha256 hash - if the
     exact same photo is searched again inside the TTL window, we skip
     Cloudinary + SerpApi entirely and reuse the previous result.
  2. Google Shopping offers keyed by the generated text query - two
     different photos of the "same" product resolve to the same query and
     shouldn't each cost a fresh Shopping API call.

Kept dependency-free (just the existing SQLAlchemy session) rather than
adding Redis or another moving part - appropriate for this project's scale,
and it's a one-line swap later if that ever changes (only this module would
need to change).

PERF: an in-process L1 layer (`_local_cache`) sits in front of the
search_cache table (L2). Every get_cached() was previously a DB round trip
even for a key just read a moment ago in the same process - and
price_service.fetch_offers_for_query's own docstring already notes it's
sometimes called twice for the same query within a single search
(brand-resolution + price enrichment both want the same offers). L1 turns
that second call into a plain dict lookup instead of a SQLite read + JSON
decode. Correctness: set_cached() writes through to L1 immediately, so a
fresh write is always visible in this process right away, and every L1
entry expires no later than the real DB row's own expires_at, so an L1 hit
never returns data staler than a DB hit would have.
"""

import json
import logging
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SearchCache

logger = logging.getLogger(__name__)

# --- L1: in-process cache -----------------------------------------------
# (bind_id, key) -> (value, monotonic_expiry_seconds). Namespaced by the
# id() of the Session's underlying Engine, not just the cache key - a
# lookup against one database must never be answered from a value written
# for a different one. In normal deployment there's exactly one Engine per
# process (see app/database.py), so this namespacing is free; it only
# matters for the (rarer, but real) case of more than one engine/database
# coexisting in the same process. Bounded by a hard entry cap (cleared
# wholesale on overflow), same "pure speed optimization, never a wrong
# answer" reasoning as the embedding-vector cache in product_index/service.py.
_LOCAL_CACHE_MAX_ENTRIES = 2_000
_local_cache: dict[tuple[int, str], tuple[object, float]] = {}

def _local_key(db: Session, key: str) -> tuple[int, str]:
    return (id(db.get_bind()), key)

def _local_get(db: Session, key: str):
    entry = _local_cache.get(_local_key(db, key))
    if entry is None:
        return None
    value, expires_at = entry
    if time.monotonic() >= expires_at:
        _local_cache.pop(_local_key(db, key), None)
        return None
    return value

def _local_set(db: Session, key: str, value, ttl_seconds: float) -> None:
    if ttl_seconds <= 0:
        return
    if len(_local_cache) >= _LOCAL_CACHE_MAX_ENTRIES:
        _local_cache.clear()
    _local_cache[_local_key(db, key)] = (value, time.monotonic() + ttl_seconds)

def get_cached(db: Session, key: str):
    """Returns the cached value (already json.loads'd) or None if missing/expired."""
    local_hit = _local_get(db, key)
    if local_hit is not None:
        return local_hit

    row = db.query(SearchCache).filter(SearchCache.cache_key == key).first()
    if row is None:
        return None

    now = datetime.now(timezone.utc)
    expires_at = row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    if expires_at < now:
        logger.info("Cache expired for key=%s", key)
        return None

    try:
        value = json.loads(row.payload_json)
    except (TypeError, ValueError):
        logger.warning("Cache payload for key=%s was corrupted, ignoring", key)
        return None

    _local_set(db, key, value, (expires_at - now).total_seconds())
    return value

def set_cached(db: Session, key: str, value, ttl_seconds: int | None = None) -> None:
    """Upserts a cache entry. Failures here should never break the request,
    caching is a performance optimization, not a correctness requirement."""
    ttl = ttl_seconds if ttl_seconds is not None else settings.cache_ttl_seconds
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl)

    try:
        payload_json = json.dumps(value)
    except (TypeError, ValueError) as e:
        logger.warning("Could not serialize cache value for key=%s: %s", key, e)
        return

    try:
        row = db.query(SearchCache).filter(SearchCache.cache_key == key).first()
        if row is None:
            row = SearchCache(cache_key=key, payload_json=payload_json, expires_at=expires_at)
            db.add(row)
        else:
            row.payload_json = payload_json
            row.expires_at = expires_at
        db.commit()
    except Exception as e:
        logger.warning("Failed to write cache key=%s: %s", key, e)
        db.rollback()
        return

    # Write-through: subsequent get_cached() calls for this key against this
    # same database, in this process, see the fresh value immediately,
    # without waiting on a DB read.
    _local_set(db, key, value, ttl)

