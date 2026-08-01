"""
Turns raw DB state into the lightweight, already-summarized snapshots
RankingContext carries (UserPreferenceSnapshot, SearchHistorySnapshot).

This is the one module under app/services/ranking/ that touches a
SQLAlchemy Session - deliberately isolated here so every RankingSignal
(see signals/) stays pure, DB-free, and unit-testable with hand-built
contexts. Nothing here is allowed to break a live search: both functions
return None on "nothing to report" rather than raising, matching the rest
of the app's hot-path conventions (see product_index/service.py).
"""

import json
import logging

from sqlalchemy.orm import Session

from app.database import SearchLog, UserPreference
from app.services import preferences_service
from app.services.ranking.types import SearchHistorySnapshot, UserPreferenceSnapshot

logger = logging.getLogger(__name__)

_SEARCH_HISTORY_LOOKBACK = 50


def load_user_preferences(db: Session, user_id: int | None) -> UserPreferenceSnapshot | None:
    if user_id is None:
        return None
    pref: UserPreference | None = preferences_service.get_preferences(db, user_id)
    if pref is None:
        return None
    return UserPreferenceSnapshot(
        favorite_categories=preferences_service.loads_json_list(pref.favorite_categories_json),
        preferred_platforms=preferences_service.loads_json_list(pref.preferred_platforms_json),
        budget_min=pref.budget_min,
        budget_max=pref.budget_max,
        shopping_style=pref.shopping_style,
    )


def load_search_history_snapshot(db: Session, user_id: int | None) -> SearchHistorySnapshot | None:
    """Frequency-counts brand/category mentions across this user's recent
    completed searches (their own product_query/detected_brand fields, and
    every result product's brand) - see SearchHistorySignal for how these
    counts get turned into a score. Returns None rather than an empty
    snapshot when there's simply no history yet, so the signal can tell
    "never searched" apart from "searched, but nothing matched"."""
    if user_id is None:
        return None

    # PERF: only select the columns this function actually reads. A full
    # SearchLog row carries columns this loop never touches (image_filename,
    # execution_time_ms, best_deal_price, ...) - for up to 50 rows on every
    # ranked search for a logged-in user, hydrating full ORM objects for
    # unused columns is pure overhead. with_entities keeps the same
    # ordering/limit/filter semantics, just narrower.
    logs = (
        db.query(SearchLog.product_query, SearchLog.detected_brand, SearchLog.results_json)
        .filter(SearchLog.user_id == user_id, SearchLog.results_json.isnot(None))
        .order_by(SearchLog.created_at.desc())
        .limit(_SEARCH_HISTORY_LOOKBACK)
        .all()
    )
    if not logs:
        return None

    brand_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    query_terms: list[str] = []

    for product_query, detected_brand, results_json in logs:
        if product_query:
            query_terms.append(product_query)
            category = preferences_service.categorize_text(product_query)
            if category:
                category_counts[category] = category_counts.get(category, 0) + 1

        if detected_brand:
            key = detected_brand.strip().lower()
            brand_counts[key] = brand_counts.get(key, 0) + 1

        try:
            items = json.loads(results_json or "[]")
        except (json.JSONDecodeError, TypeError):
            items = []
        for item in items:
            brand = (item or {}).get("brand")
            if brand:
                key = brand.strip().lower()
                brand_counts[key] = brand_counts.get(key, 0) + 1

    if not brand_counts and not category_counts:
        return None

    return SearchHistorySnapshot(
        brand_counts=brand_counts,
        category_counts=category_counts,
        query_terms=query_terms[:20],
    )
