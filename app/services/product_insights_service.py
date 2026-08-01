"""
Per-product analytics for the Product Analytics page.

Three pieces, each honest about what it actually is:

1. Price history - real points read from ProductPriceHistory (the same
   table app/services/price_history_service.py already writes to). If a
   product has fewer than two recorded points, we say so instead of
   drawing a fake trend line.
2. Review sentiment - a bucketed *estimate* derived from the average star
   rating, used as a fallback when real review text can't be found. Real,
   per-review-text sentiment analysis (fetched via SerpApi + scored with
   VADER) lives in app/services/review_sentiment_service.py and is tried
   first - this function is only ever reached when that comes up empty.
   The response always labels which of the two it actually got.
3. Quick summary - a handful of rule-based bullet points (price trend +
   rating tier). Not an LLM call; deterministic and cheap on purpose.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.database import ProductPriceHistory
from app.models import PriceTrendPoint, ReviewSentiment
from app.services.price_history_service import normalize_product_key

logger = logging.getLogger(__name__)

def get_price_history_points(
    db: Session, product_name: str, limit: int = 30
) -> list[PriceTrendPoint]:
    """Every real, previously-recorded price point for this product,
    oldest first. Empty list if we've never tracked it before."""
    product_key = normalize_product_key(product_name)
    if not product_key:
        return []

    try:
        rows = (
            db.query(ProductPriceHistory)
            .filter(ProductPriceHistory.product_key == product_key)
            .order_by(ProductPriceHistory.created_at.asc())
            .limit(limit)
            .all()
        )
    except Exception:
        logger.exception("Failed to load price history for product=%s", product_name)
        return []

    return [
        PriceTrendPoint(
            price=row.price,
            currency=row.currency,
            marketplace=row.marketplace,
            recorded_at=row.created_at,
        )
        for row in rows
    ]

_SENTIMENT_BUCKETS: list[tuple[float, int, int, int]] = [
    (4.5, 88, 9, 3),
    (4.0, 75, 17, 8),
    (3.5, 58, 25, 17),
    (3.0, 42, 30, 28),
    (0.0, 22, 26, 52),
]

def estimate_sentiment(
    rating: float | None, review_count: int | None
) -> ReviewSentiment | None:
    """Returns None (rather than a guessed split) when there's no rating
    to base an estimate on at all."""
    if rating is None:
        return None

    for threshold, positive, neutral, negative in _SENTIMENT_BUCKETS:
        if rating >= threshold:
            basis = f"Estimated from the {rating:.1f}-star average"
            if review_count:
                basis += f" across {review_count:,} reviews"
            basis += " - individual review text isn't analyzed."
            return ReviewSentiment(
                positive_pct=positive,
                neutral_pct=neutral,
                negative_pct=negative,
                basis=basis,
                is_estimate=True,
            )

    return None

def price_trend(
    price_points: list[PriceTrendPoint],
) -> tuple[str | None, float | None]:
    """direction ("up"/"down"/"same") + percent change, first vs last
    recorded point. None/None if there aren't at least two points."""
    if len(price_points) < 2:
        return None, None

    first, last = price_points[0].price, price_points[-1].price
    change_percent = round(((last - first) / first) * 100, 2) if first else None

    if last > first:
        return "up", change_percent
    if last < first:
        return "down", change_percent
    return "same", 0.0

def build_summary(
    *,
    rating: float | None,
    review_count: int | None,
    price_points: list[PriceTrendPoint],
) -> tuple[list[str], str]:
    """Returns (bullet insights, one-line verdict)."""
    bullets: list[str] = []
    direction, change_percent = price_trend(price_points)

    if direction == "down":
        bullets.append(
            f"Price is falling ({abs(change_percent):.0f}% lower than when we first tracked it)."
        )
    elif direction == "up":
        bullets.append(
            f"Price is rising ({change_percent:.0f}% higher than when we first tracked it)."
        )
    elif direction == "same":
        bullets.append("Price has stayed steady across the searches we've tracked.")
    else:
        bullets.append("Not enough price history yet - check back after this product is searched again.")

    rating_tier: str | None = None
    if rating is not None:
        if rating >= 4.5:
            rating_tier = "excellent"
            bullets.append("Excellent reviews from shoppers.")
        elif rating >= 4.0:
            rating_tier = "good"
            bullets.append("Good reviews overall.")
        elif rating >= 3.0:
            rating_tier = "mixed"
            bullets.append("Reviews are mixed - worth reading a few before buying.")
        else:
            rating_tier = "poor"
            bullets.append("Below-average reviews for this listing.")
    else:
        bullets.append("No rating data available for this listing.")

    if rating_tier == "poor" or direction == "up":
        verdict = "Better to wait"
    elif direction in ("down", "same") and rating_tier in ("excellent", "good"):
        verdict = "Worth buying now"
    else:
        verdict = "Good option - compare a couple more sellers first"

    return bullets[:3], verdict
