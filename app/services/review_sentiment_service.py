"""
Real, per-review-text sentiment analysis.

Where product_insights_service.estimate_sentiment() derives a *guessed*
positive/neutral/negative split from the star rating alone (there being no
review text available to it), this module fetches actual review text via
SerpApi's Google Immersive Product API and scores it with VADER - a
lexicon+rule-based sentiment analyzer tuned for short, informal text like
product reviews and social media, chosen specifically because it needs no
model training or hosting and runs in milliseconds per review.

Flow for one product:
  1. fetch_offers_for_query(title, db) - reuses the exact same cached
     Google Shopping call app/services/price_service.py already makes for
     this title, so looking up review-fetchability doesn't cost an extra
     SerpApi unit by itself.
  2. Pick the offer whose immersive_product_page_token belongs to the
     specific listing being viewed (preferring an exact link match, then a
     platform match, then just the first offer that has one at all).
  3. google_immersive_product(page_token) -> extract_user_reviews() - one
     more SerpApi unit. Cached separately from the shopping-query cache and
     with a longer TTL (settings.review_sentiment_cache_ttl_seconds) since
     review text for a product is far more stable than its price.
  4. Score each review's title+text with VADER, bucket by compound score,
     aggregate into percentages, and keep one real positive and one real
     negative snippet so the UI can show its work.

Falls back to product_insights_service.estimate_sentiment() (the honest
rating-bucket estimate) whenever real review text can't be found or there
isn't enough of it to trust - this module never fabricates a text-based
result, and the returned ReviewSentiment.is_estimate always says truthfully
which path was actually taken.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from app.config import settings
from app.models import ReviewSentiment
from app.services import cache_service, product_insights_service
from app.services.domain_filter import match_trusted_platform
from app.services.price_service import fetch_offers_for_query
from app.services.serpapi_client import SerpApiError, extract_user_reviews, google_immersive_product

logger = logging.getLogger(__name__)

_analyzer = SentimentIntensityAnalyzer()

# VADER's own documented thresholds for classifying a compound score.
_POSITIVE_THRESHOLD = 0.05
_NEGATIVE_THRESHOLD = -0.05

_SNIPPET_CHAR_LIMIT = 220

def _select_page_token(offers: list[dict], *, platform: str | None, link: str | None) -> str | None:
    """Best-effort match of a Google Shopping offer to the specific listing
    being viewed, so the reviews fetched are for the right product rather
    than an arbitrary top result for the query text."""

    def has_token(offer: dict) -> bool:
        return bool(offer.get("page_token"))

    if link:
        for offer in offers:
            if has_token(offer) and offer.get("link") == link:
                return offer["page_token"]

    if platform:
        normalized_platform = platform.strip().lower()
        for offer in offers:
            if not has_token(offer):
                continue
            if match_trusted_platform(offer.get("link") or "") == platform:
                return offer["page_token"]
            if (offer.get("source") or "").strip().lower() == normalized_platform:
                return offer["page_token"]

    for offer in offers:
        if has_token(offer):
            return offer["page_token"]

    return None

def _fetch_reviews(db: Session, page_token: str) -> list[dict]:
    """Cached wrapper around google_immersive_product + extract_user_reviews."""
    cache_key = f"immersive_reviews:{page_token}"
    cached = cache_service.get_cached(db, cache_key)
    if cached is not None:
        return cached

    try:
        response = google_immersive_product(page_token)
        reviews = extract_user_reviews(response)
    except SerpApiError as e:
        logger.warning("Immersive product review lookup failed: %s", e)
        return []

    cache_service.set_cached(
        db, cache_key, reviews, ttl_seconds=settings.review_sentiment_cache_ttl_seconds
    )
    return reviews

def _score_review(review: dict) -> str:
    """positive / neutral / negative for one review's text. The title is
    included when present (e.g. "Great TV" is often the most
    sentiment-dense part of a review) alongside the body."""
    combined = " ".join(part for part in (review.get("title"), review.get("text")) if part)
    compound = _analyzer.polarity_scores(combined)["compound"]
    if compound >= _POSITIVE_THRESHOLD:
        return "positive"
    if compound <= _NEGATIVE_THRESHOLD:
        return "negative"
    return "neutral"

def _trim(text: str | None) -> str | None:
    if not text:
        return None
    text = text.strip()
    if len(text) <= _SNIPPET_CHAR_LIMIT:
        return text
    return text[: _SNIPPET_CHAR_LIMIT - 1].rstrip() + "…"

def _build_real_sentiment(reviews: list[dict]) -> ReviewSentiment:
    scored = [(review, _score_review(review)) for review in reviews]
    n = len(scored)

    positive = sum(1 for _, label in scored if label == "positive")
    negative = sum(1 for _, label in scored if label == "negative")

    positive_pct = round(positive / n * 100)
    negative_pct = round(negative / n * 100)
    neutral_pct = 100 - positive_pct - negative_pct  # absorbs rounding drift

    sample_positive = next((review["text"] for review, label in scored if label == "positive"), None)
    sample_negative = next((review["text"] for review, label in scored if label == "negative"), None)

    return ReviewSentiment(
        positive_pct=positive_pct,
        neutral_pct=neutral_pct,
        negative_pct=negative_pct,
        basis=f"Real text analysis of {n} actual review{'s' if n != 1 else ''} for this listing (VADER sentiment scoring).",
        is_estimate=False,
        review_count_analyzed=n,
        sample_positive=_trim(sample_positive),
        sample_negative=_trim(sample_negative),
    )

def get_sentiment(
    db: Session,
    *,
    title: str,
    platform: str | None,
    link: str | None,
    rating: float | None,
    review_count: int | None,
) -> ReviewSentiment | None:
    """Main entrypoint (called from app/routers/products.py). Tries real
    review-text sentiment first; falls back to the rating-bucket estimate
    when real text isn't available, there isn't enough of it, or the
    SerpApi lookup fails for any reason. Never raises - a sentiment lookup
    failing should never break the rest of the product analytics page."""
    if settings.enable_real_review_sentiment:
        try:
            offers = fetch_offers_for_query(title, db)
            page_token = _select_page_token(offers, platform=platform, link=link)
            if page_token:
                reviews = _fetch_reviews(db, page_token)
                if len(reviews) >= settings.review_sentiment_min_reviews:
                    return _build_real_sentiment(reviews[: settings.review_sentiment_max_reviews])
        except Exception:
            logger.exception("Real review sentiment lookup failed for title=%s", title)

    return product_insights_service.estimate_sentiment(rating, review_count)
