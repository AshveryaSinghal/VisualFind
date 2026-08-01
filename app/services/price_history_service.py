"""
Price tracking across searches.

Every time a search resolves a best-deal product (a real price, on a real
trusted marketplace), we store {product name, marketplace, price, timestamp}
in ProductPriceHistory (app/database.py). The next time the *same* product
is searched (matched by a normalized product-name key), we compare the new
price against the most recent prior entry and report the difference.

This is intentionally simple and does not do analytics or trend charts -
just a single previous-vs-current comparison, per the spec.
"""

import logging
import re

from sqlalchemy.orm import Session

from app.database import ProductPriceHistory
from app.models import PriceHistoryComparison

logger = logging.getLogger(__name__)

_NORMALIZE_STOPWORDS = {
    "the", "a", "an", "for", "with", "and", "buy", "online", "new",
    "genuine", "original", "combo", "pack", "set",
}

def normalize_product_key(name: str) -> str:
    """Lowercase, strip punctuation, drop filler words, collapse whitespace."""
    if not name:
        return ""
    cleaned = re.sub(r"[^a-z0-9\s]", " ", name.lower())
    tokens = [t for t in cleaned.split() if t and t not in _NORMALIZE_STOPWORDS]
    return " ".join(tokens)

def _pct_change(previous: float, current: float) -> float:
    if previous == 0:
        return 0.0
    return round(((current - previous) / previous) * 100, 2)

def record_and_compare(
    db: Session,
    *,
    product_name: str | None,
    marketplace: str | None,
    price: float | None,
    currency: str | None,
    user_id: int | None = None,
) -> PriceHistoryComparison | None:
    """
    Persists this search's product/price and returns a comparison against
    the last time the same product was tracked. Returns None only if there
    is nothing meaningful to track (no product name or no price found) -
    the caller should simply omit price_history in that case rather than
    fabricating a comparison.
    """
    if not product_name or price is None:
        return None

    product_key = normalize_product_key(product_name)
    if not product_key:
        return None

    marketplace = marketplace or "Unknown"

    try:
        previous = (
            db.query(ProductPriceHistory)
            .filter(ProductPriceHistory.product_key == product_key)
            .order_by(ProductPriceHistory.created_at.desc())
            .first()
        )

        entry = ProductPriceHistory(
            user_id=user_id,
            product_key=product_key,
            product_name=product_name,
            marketplace=marketplace,
            price=price,
            currency=currency,
        )
        db.add(entry)
        db.commit()
    except Exception:
        logger.exception("Price history tracking failed for product=%s", product_name)
        db.rollback()
        return None

    try:
        from app.services.alert_service import check_and_trigger_alerts

        check_and_trigger_alerts(
            db,
            product_key=product_key,
            price=price,
            marketplace=marketplace,
            currency=currency,
        )
    except Exception:
        logger.exception("Price alert check failed for product=%s", product_name)

    if previous is None:
        return PriceHistoryComparison(
            first_time=True,
            message="This is the first tracked price.",
            product_name=product_name,
            current_price=price,
            current_marketplace=marketplace,
        )

    change_percent = _pct_change(previous.price, price)
    if price > previous.price:
        direction = "up"
        message = (
            f"Price increased {change_percent:.1f}% since it was last tracked "
            f"({previous.marketplace}, {previous.price:g} -> {marketplace}, {price:g})."
        )
    elif price < previous.price:
        direction = "down"
        message = (
            f"Price dropped {abs(change_percent):.1f}% since it was last tracked "
            f"({previous.marketplace}, {previous.price:g} -> {marketplace}, {price:g})."
        )
    else:
        direction = "same"
        message = "Price is unchanged since it was last tracked."

    return PriceHistoryComparison(
        first_time=False,
        message=message,
        product_name=product_name,
        previous_price=previous.price,
        previous_marketplace=previous.marketplace,
        previous_checked_at=previous.created_at,
        current_price=price,
        current_marketplace=marketplace,
        change_percent=change_percent,
        direction=direction,
    )
