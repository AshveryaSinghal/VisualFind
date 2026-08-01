"""
Personalized recommendations built entirely from a user's own real activity
- past searches, products they've opened, products they've compared, and
their saved preferences (see app/services/preferences_service.py). There is
no product catalog to recommend *from*, so recommendations are always real
PurchaseLink entries the person's own searches have already surfaced -
never fabricated or fetched fresh from a third party. This mirrors the rest
of the app's "only ever show real data, be upfront about where it came
from" philosophy (see price_history_service, product_insights_service).
"""

import json
import logging
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database import ComparedProduct, SearchLog, UserPreference, ViewedProduct
from app.models import PurchaseLink, RecommendationItem, RecommendationReason, RecommendationsResponse
from app.services import preferences_service
from app.services.price_history_service import normalize_product_key
from app.services.price_utils import extract_numeric_price

logger = logging.getLogger(__name__)

_MAX_ITEMS = 12
_LOOKBACK_LOGS = 40

def _product_key(product: PurchaseLink) -> str:
    return f"{(product.platform or '').lower()}::{(product.link or product.title or '').lower()}"

def _within_budget(price: float | None, budget_min: float | None, budget_max: float | None) -> bool:
    if price is None:
        return True
    if budget_min is not None and price < budget_min:
        return False
    if budget_max is not None and price > budget_max:
        return False
    return True

def _shopping_style_sort_key(shopping_style: str | None):
    def key(product: PurchaseLink):
        price = extract_numeric_price(product.price) or float("inf")
        rating = product.rating or 0.0
        reviews = product.review_count or 0
        if shopping_style == "lowest_price":
            return (price, -rating)
        if shopping_style == "highest_rating":
            return (-rating, -reviews)
        if shopping_style == "premium":
            return (-price, -rating)

        return (0 if product.is_best_deal else 1, -rating, price)

    return key

def _collect_products_from_logs(db: Session, user_id: int) -> list[tuple[PurchaseLink, str | None]]:
    """Every product from the user's recent search results, paired with the
    product_query that surfaced it."""
    logs = (
        db.query(SearchLog)
        .filter(SearchLog.user_id == user_id, SearchLog.results_json.isnot(None))
        .order_by(SearchLog.created_at.desc())
        .limit(_LOOKBACK_LOGS)
        .all()
    )
    pool: list[tuple[PurchaseLink, str | None]] = []
    for log in logs:
        try:
            items = json.loads(log.results_json or "[]")
        except (json.JSONDecodeError, TypeError):
            continue
        for item in items:
            try:
                pool.append((PurchaseLink(**item), log.product_query))
            except Exception:
                continue
    return pool

def build_recommendations(db: Session, user_id: int) -> RecommendationsResponse:
    pref_row: UserPreference | None = preferences_service.get_preferences(db, user_id)
    favorite_categories = preferences_service.loads_json_list(pref_row.favorite_categories_json) if pref_row else []
    preferred_platforms = set(preferences_service.loads_json_list(pref_row.preferred_platforms_json)) if pref_row else set()
    budget_min = pref_row.budget_min if pref_row else None
    budget_max = pref_row.budget_max if pref_row else None
    shopping_style = pref_row.shopping_style if pref_row else None

    pool = _collect_products_from_logs(db, user_id)

    recent_search_logs = (
        db.query(SearchLog)
        .filter(SearchLog.user_id == user_id, SearchLog.product_query.isnot(None))
        .order_by(SearchLog.created_at.desc())
        .limit(_LOOKBACK_LOGS)
        .all()
    )
    viewed_count = db.query(ViewedProduct).filter(ViewedProduct.user_id == user_id).count()
    compared_count = db.query(ComparedProduct).filter(ComparedProduct.user_id == user_id).count()

    has_enough_signal = bool(pool or favorite_categories or viewed_count or compared_count)

    used_keys: set[str] = set()
    items: list[RecommendationItem] = []

    seen_queries: list[str] = []
    for log in recent_search_logs:
        query = (log.product_query or "").strip()
        if not query or query.lower() in [q.lower() for q in seen_queries]:
            continue
        seen_queries.append(query)
        if len(seen_queries) > 4:
            break

        try:
            log_items = [PurchaseLink(**i) for i in json.loads(log.results_json or "[]")]
        except (json.JSONDecodeError, TypeError):
            continue
        if not log_items:
            continue
        best = next((p for p in log_items if p.is_best_deal), None) or max(
            log_items, key=lambda p: (p.rating or 0, p.review_count or 0)
        )
        key = _product_key(best)
        if key in used_keys:
            continue
        used_keys.add(key)
        items.append(
            RecommendationItem(
                reason_type=RecommendationReason.SEARCH_HISTORY,
                reason_text=f'Because you searched for "{query}"',
                product=best,
            )
        )

    for category_value in favorite_categories[:3]:
        label = preferences_service.CATEGORY_KEYWORDS.get(category_value, (category_value, []))[0]
        candidates = [
            product
            for product, query in pool
            if preferences_service.categorize_text(product.title) == category_value
            or preferences_service.categorize_text(query) == category_value
        ]
        candidates = [p for p in candidates if _product_key(p) not in used_keys]
        candidates = [
            p for p in candidates if _within_budget(extract_numeric_price(p.price), budget_min, budget_max)
        ]
        if not candidates:
            continue
        candidates.sort(key=lambda p: (-(p.rating or 0), -(p.review_count or 0)))
        pick = candidates[0]
        key = _product_key(pick)
        used_keys.add(key)
        items.append(
            RecommendationItem(
                reason_type=RecommendationReason.CATEGORY,
                reason_text=f"Trending in your favorite category: {label}",
                category=category_value,
                product=pick,
            )
        )

    remaining = [product for product, _query in pool if _product_key(product) not in used_keys]
    remaining = [
        p for p in remaining if _within_budget(extract_numeric_price(p.price), budget_min, budget_max)
    ]

    def score(p: PurchaseLink) -> tuple:
        platform_boost = 0 if (p.platform in preferred_platforms) else 1
        style_key = _shopping_style_sort_key(shopping_style)(p)
        return (platform_boost, *([style_key] if isinstance(style_key, tuple) else [style_key]))

    dedup: dict[str, PurchaseLink] = {}
    for p in remaining:
        k = _product_key(p)
        if k not in dedup:
            dedup[k] = p
    ranked = sorted(dedup.values(), key=score)

    style_label = preferences_service.SHOPPING_STYLE_LABELS.get(shopping_style, "picked for you")
    slots_left = max(0, _MAX_ITEMS - len(items))
    for p in ranked[:slots_left]:
        key = _product_key(p)
        if key in used_keys:
            continue
        used_keys.add(key)
        reason = "You may also like..." if not shopping_style else f"You may also like... ({style_label})"
        items.append(
            RecommendationItem(
                reason_type=RecommendationReason.VIEWED,
                reason_text=reason,
                product=p,
            )
        )

    return RecommendationsResponse(
        items=items[:_MAX_ITEMS],
        has_enough_signal=has_enough_signal,
        generated_at=datetime.now(timezone.utc),
    )
