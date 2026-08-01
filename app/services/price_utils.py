"""
Data-quality helpers for product results: price/currency/rating/merchant
normalization, deduplication, sorting, and "best deal" marking.

Kept dependency-free (stdlib only) on purpose - this is pure data
transformation, no I/O, so it's trivially unit-testable.
"""

import re

_BRAND_STOPWORDS = {
    "the", "new", "best", "original", "genuine", "combo", "pack", "set",
    "for", "with", "and", "buy", "online", "premium", "pure", "a", "an",
    "official", "store",
}

def guess_brand(title: str | None, platform: str | None = None) -> str | None:
    """Best-effort brand guess from a product title.

    Takes the first capitalized word that isn't a generic e-commerce
    stopword - e.g. "Sony WH-1000XM5 Headphones" -> "Sony". Falls back to
    the platform name for an "official <brand> store" style result, where
    the brand *is* the platform. Returns None rather than guessing wrong.
    """
    if platform and "official" in platform.lower():
        brand_from_platform = re.sub(r"(?i)\bofficial\b|\bstore\b", "", platform).strip()
        if brand_from_platform:
            return brand_from_platform

    if not title:
        return None

    for word in title.split():
        cleaned = re.sub(r"[^A-Za-z0-9\-]", "", word)
        if not cleaned or cleaned.lower() in _BRAND_STOPWORDS:
            continue
        if cleaned[0].isupper() or cleaned.isupper():
            return cleaned
        break

    return None

def extract_numeric_price(price) -> float | None:
    """
    Converts different price formats into a float.

    Examples
        "₹1,299"  -> 1299.0
        "1,299"   -> 1299.0
        1299      -> 1299.0
        None      -> None
    """
    if price is None:
        return None

    if isinstance(price, (int, float)):
        return float(price)

    price = str(price)
    match = re.search(r"[\d,.]+", price)
    if not match:
        return None

    value = match.group(0).replace(",", "")

    if value in ("", "."):
        return None

    try:
        return float(value)
    except ValueError:
        return None

def normalize_rating(raw_rating) -> float | None:
    """Parses things like 4.5, "4.5", "4.5 out of 5 stars" into a 0-5 float."""
    if raw_rating is None:
        return None
    if isinstance(raw_rating, (int, float)):
        value = float(raw_rating)
    else:
        match = re.search(r"[\d.]+", str(raw_rating))
        if not match:
            return None
        try:
            value = float(match.group(0))
        except ValueError:
            return None

    if value < 0:
        return None
    return round(min(value, 5.0), 2)

def normalize_review_count(raw_count) -> int | None:
    """Parses "1,234", "1.2K", 1234 into an int. Returns None if unparseable."""
    if raw_count is None:
        return None
    if isinstance(raw_count, int):
        return raw_count
    if isinstance(raw_count, float):
        return int(raw_count)

    text = str(raw_count).strip().lower().replace(",", "")
    match = re.search(r"([\d.]+)\s*(k|m)?", text)
    if not match:
        return None

    try:
        value = float(match.group(1))
    except ValueError:
        return None

    suffix = match.group(2)
    if suffix == "k":
        value *= 1_000
    elif suffix == "m":
        value *= 1_000_000

    return int(value)

def annotate_quick_commerce(purchase_links: list) -> list:
    """Sets is_quick_commerce / delivery_estimate on every PurchaseLink whose
    platform is a known quick-commerce platform (Blinkit, Zepto, Instamart).
    Mutates and returns the same list for convenience."""
    from app.services.domain_filter import is_quick_commerce, quick_commerce_delivery_estimate

    for link in purchase_links:
        if is_quick_commerce(link.platform):
            link.is_quick_commerce = True
            link.delivery_estimate = quick_commerce_delivery_estimate(link.platform)
    return purchase_links

def pick_fastest_delivery(purchase_links: list):
    """Cheapest priced listing among quick-commerce platforms, or None if no
    quick-commerce listing (priced or not) is present in the results."""
    quick_commerce_priced = [
        link for link in purchase_links if link.is_quick_commerce and link.price is not None
    ]
    if not quick_commerce_priced:
        return None
    return min(quick_commerce_priced, key=lambda link: extract_numeric_price(link.price) or float("inf"))

def normalize_merchant_name(name: str | None) -> str | None:
    if not name:
        return name
    return " ".join(name.split()).strip()

def dedupe_products(products: list[dict]) -> list[dict]:
    """
    Removes duplicate product entries.

    Primary key: exact link. Secondary key: (platform, rounded price) since
    the same product can arrive twice with slightly different tracking
    params on the URL (once from Lens, once from Google Shopping). First
    occurrence wins, and entries are ordered so Shopping-sourced (live,
    richer) data wins over Lens-only fallback data - see price_service.py,
    which appends Shopping-only matches after enriching Lens candidates in
    place, so "first occurrence" here still means "best available data".
    """
    seen_links: set[str] = set()
    seen_secondary: set[tuple] = set()
    deduped: list[dict] = []

    for product in products:
        link = (product.get("link") or "").strip().rstrip("/")
        if link and link in seen_links:
            continue

        price_value = extract_numeric_price(product.get("price"))
        secondary_key = (product.get("platform"), round(price_value, 2) if price_value is not None else None)
        title = (product.get("title") or "").strip().lower()
        secondary_key = secondary_key + (title,)

        if secondary_key in seen_secondary and price_value is not None:
            continue

        if link:
            seen_links.add(link)
        seen_secondary.add(secondary_key)
        deduped.append(product)

    return deduped

def sort_by_price(products):
    """Lowest price first. Products without a price go last."""
    return sorted(
        products,
        key=lambda p: (
            extract_numeric_price(p.price) is None,
            extract_numeric_price(p.price) or float("inf"),
        ),
    )

def apply_sort(products, sort_by: str | None):
    """
    Backend support for the sort orders the frontend can offer later:
    price_low, price_high, rating, reviews, platform.

    Unknown or missing sort_by falls back to price_low (the app's default,
    since "cheapest first" is the whole point of the best-deal feature).
    """
    if sort_by == "price_high":
        return sorted(
            products,
            key=lambda p: (
                extract_numeric_price(p.price) is None,
                -(extract_numeric_price(p.price) or 0),
            ),
        )
    if sort_by == "rating":
        return sorted(
            products,
            key=lambda p: (p.rating is None, -(p.rating or 0)),
        )
    if sort_by == "reviews":
        return sorted(
            products,
            key=lambda p: (p.review_count is None, -(p.review_count or 0)),
        )
    if sort_by == "platform":
        return sorted(products, key=lambda p: (p.platform or "").lower())

    return sort_by_price(products)

def _normalized(value: float | None, low: float, high: float) -> float:
    """Maps value into 0.0-1.0 given the observed low/high across candidates.
    Returns 0.5 (neutral) when there's no spread or no value to compare."""
    if value is None or high <= low:
        return 0.5
    return max(0.0, min(1.0, (value - low) / (high - low)))

_WEIGHT_PRICE = 0.35
_WEIGHT_RATING = 0.2
_WEIGHT_REVIEWS = 0.15
_WEIGHT_DISCOUNT = 0.15
_WEIGHT_CREDIBILITY = 0.15

def _score_candidate(product, price, lowest_price, highest_price, max_reviews) -> float:
    import math

    from app.services.domain_filter import seller_credibility

    price_score = 1.0 - _normalized(price, lowest_price, highest_price)
    rating_score = _normalized(product.rating, 0.0, 5.0) if product.rating is not None else 0.4
    review_score = (
        _normalized(math.log1p(product.review_count), 0.0, math.log1p(max_reviews))
        if product.review_count and max_reviews
        else 0.3
    )
    discount_score = _normalized(highest_price - price, 0.0, max(highest_price - lowest_price, 1.0))
    credibility_score = seller_credibility(product.platform)

    return (
        _WEIGHT_PRICE * price_score
        + _WEIGHT_RATING * rating_score
        + _WEIGHT_REVIEWS * review_score
        + _WEIGHT_DISCOUNT * discount_score
        + _WEIGHT_CREDIBILITY * credibility_score
    )

def _build_best_deal_reason(product, price, lowest_price, highest_price) -> str:
    """Short, human-readable explanation of *why* this product won, so the
    UI never just says "best deal" with no justification."""
    reasons: list[str] = []

    if price == lowest_price:
        reasons.append("lowest price among trusted sellers")
    elif highest_price > lowest_price:
        pct_below_top = round((1 - price / highest_price) * 100)
        if pct_below_top > 0:
            reasons.append(f"{pct_below_top}% cheaper than the priciest listing")

    if product.rating is not None and product.rating >= 4.0:
        reasons.append(f"highly rated at {product.rating:.1f}★")
    if product.review_count:
        reasons.append(f"backed by {product.review_count:,} reviews")

    from app.services.domain_filter import seller_credibility

    if seller_credibility(product.platform) >= 0.9:
        reasons.append(f"sold on a highly credible platform ({product.platform})")

    if not reasons:
        return "Best overall balance of price, rating, and seller trust among the available options."

    if len(reasons) == 1:
        return f"Chosen for its {reasons[0]}."
    return "Chosen for its " + ", ".join(reasons[:-1]) + f", and {reasons[-1]}."

def mark_best_deal(products):
    """
    Runs the Best Deal engine over every priced product: a weighted score
    across price, rating, review count, discount vs. the priciest listing,
    and seller credibility (not just "cheapest wins"). The winner is marked
    is_best_deal=True with a plain-language best_deal_reason; every other
    priced product gets its `savings` vs. the winner. Never fabricates a
    price: products without one are left alone and sort to the end.
    """
    products = sort_by_price(products)

    priced = [(p, extract_numeric_price(p.price)) for p in products]
    priced = [(p, price) for p, price in priced if price is not None]

    for product in products:
        product.is_best_deal = False
        product.savings = None
        product.best_deal_reason = None

    if not priced:
        return products

    prices = [price for _, price in priced]
    lowest_price, highest_price = min(prices), max(prices)
    max_reviews = max((p.review_count or 0) for p, _ in priced)

    scored = [
        (product, price, _score_candidate(product, price, lowest_price, highest_price, max_reviews))
        for product, price in priced
    ]
    winner, winner_price, _ = max(scored, key=lambda triple: triple[2])

    winner.is_best_deal = True
    winner.best_deal_reason = _build_best_deal_reason(winner, winner_price, lowest_price, highest_price)

    for product, price in priced:
        if product is winner:
            continue
        if price > winner_price:
            product.savings = round(price - winner_price, 2)

    return products
