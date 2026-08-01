"""
Stage 1 of the indexing pipeline: normalize metadata.

Every field on a RawProduct is best-effort cleaned here using the same
helpers the rest of the app already trusts for this (app/services/text_utils.py,
price_utils.py, preferences_service.py) rather than re-implementing
title/price/brand cleanup a second time. This runs identically regardless
of where the RawProduct came from - a Lens result and a CSV row go through
the exact same normalization.
"""

from __future__ import annotations

import logging

from app.services import preferences_service
from app.services.indexing.types import RawProduct
from app.services.price_utils import extract_numeric_price, guess_brand, normalize_merchant_name
from app.services.text_utils import clean_product_title

logger = logging.getLogger(__name__)


def normalize_raw_product(raw: RawProduct) -> RawProduct | None:
    """Returns a new, cleaned RawProduct, or None if nothing usable is
    left (no title survives cleaning - such a row can't be catalogued at
    all, since the catalog key is derived from the title).
    """
    title = clean_product_title(raw.title) if raw.title else None
    if not title:
        return None

    brand = (raw.brand or "").strip() or None
    source = normalize_merchant_name(raw.source) or (raw.source.strip() if raw.source else None)
    brand = brand or guess_brand(title, source)

    category = (raw.category or "").strip() or None
    category = category or preferences_service.categorize_text(title)

    description = (raw.description or "").strip() or None
    image_url = (raw.image_url or "").strip() or None
    product_url = (raw.product_url or "").strip() or None

    currency = (raw.currency or "").strip().upper() or None
    price = extract_numeric_price(raw.price)

    rating = None
    if raw.rating is not None:
        try:
            rating = float(raw.rating)
        except (TypeError, ValueError):
            rating = None

    review_count = None
    if raw.review_count is not None:
        try:
            review_count = int(raw.review_count)
        except (TypeError, ValueError):
            review_count = None

    return RawProduct(
        title=title,
        brand=brand,
        category=category,
        image_url=image_url,
        description=description,
        price=price,
        currency=currency,
        rating=rating,
        review_count=review_count,
        source=source,
        product_url=product_url,
        external_id=raw.external_id,
        raw=raw.raw,
    )


def normalize_batch(raw_products: list[RawProduct]) -> tuple[list[RawProduct], int]:
    """Normalizes every product in a batch. Returns (normalized, invalid_count)
    - items that normalize to None (unusable title) are dropped and counted
    rather than raising, so one bad row in a 10,000-row CSV never fails the
    whole batch."""
    normalized: list[RawProduct] = []
    invalid = 0
    for raw in raw_products:
        try:
            cleaned = normalize_raw_product(raw)
        except Exception:
            logger.debug("Failed to normalize raw product: %r", raw, exc_info=True)
            cleaned = None
        if cleaned is None:
            invalid += 1
        else:
            normalized.append(cleaned)
    return normalized, invalid
