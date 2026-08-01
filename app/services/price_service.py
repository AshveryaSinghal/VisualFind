"""
Live-price resolution for trusted shopping links.

Orchestration wrapper around app/services/price_extraction/ (the
PriceExtractionService and its tiered strategies). This module owns the
product-search-level concerns - bulk Google Shopping querying, caching,
looping over candidates, and shaping the final list of enriched product
dicts - while price_extraction/ owns the actual per-product multi-tier
extraction logic (Tiers 1-7: strategies, normalization, validation,
selection, confidence scoring).

A single platform's extraction failing (blocked page, timeout, missing
headless-browser dependency, malformed HTML, whatever) never stops the
others from being processed - each candidate is extracted independently and
wrapped in its own try/except as a second line of defense on top of the
pipeline's own internal exception safety (see price_extraction/strategies/base.py).
"""

import logging
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session

from app.config import settings
from app.services import cache_service
from app.services.currency_resolver import currency_resolver
from app.services.domain_filter import (
    build_platform_search_link,
    match_trusted_platform,
    match_trusted_platform_by_source,
)
from app.services.price_extraction import ExtractionResult, PriceExtractionService
from app.services.price_utils import (
    extract_numeric_price,
    normalize_rating,
    normalize_review_count,
)
from app.services.serpapi_client import SerpApiError, extract_shopping_offers, google_shopping_search

logger = logging.getLogger(__name__)

_price_extraction_service = PriceExtractionService()

def fetch_offers_for_query(query: str, db: Session) -> list[dict]:
    """
    Cached wrapper around google_shopping_search + extract_shopping_offers.

    Public on purpose: search_service calls this once, up front, and passes
    the result into *both* BrandResolutionService.resolve() (so the
    GOOGLE_SHOPPING_MERCHANT detection signal - detector.py's
    _from_shopping_offers - actually has data to look at) and
    enrich_with_live_prices() below. The cache_service layer means calling
    it twice for the same query is a no-op DB read, not a second SerpApi
    call - so this is free to call early.
    """
    cache_key = f"shopping_query:{query.strip().lower()}"
    cached = cache_service.get_cached(db, cache_key)
    if cached is not None:
        logger.info("Shopping Query Source: cache (query=%s)", query)
        return cached

    try:
        response = google_shopping_search(query)
        offers = extract_shopping_offers(response)
    except SerpApiError as e:
        logger.warning("Google Shopping lookup failed for query=%s: %s", query, e)
        return []

    cache_service.set_cached(db, cache_key, offers)
    return offers

def _group_offers_by_platform(offers: list[dict]) -> dict[str, list[dict]]:
    offers_by_platform: dict[str, list[dict]] = defaultdict(list)
    for offer in offers:
        platform = match_trusted_platform(offer["link"]) or match_trusted_platform_by_source(
            offer.get("source")
        )
        if platform:
            offers_by_platform[platform].append(offer)
    return offers_by_platform

def _extract_price_for_candidate(candidate: dict, offers_by_platform: dict) -> ExtractionResult:
    """
    Runs the full tiered pipeline for one candidate. Defensive on top of
    PriceExtractionService's own internal exception safety - a single
    product must never be able to take down the batch, no matter what goes
    wrong here.
    """
    try:
        return _price_extraction_service.extract(candidate, offers_by_platform=offers_by_platform)
    except Exception as e:
        logger.error(
            "Unexpected error extracting price | platform=%s url=%s error=%s",
            candidate.get("platform"), candidate.get("link"), e,
        )
        return ExtractionResult(
            price=None,
            currency=None,
            price_source="unavailable",
            extraction_method="none",
            confidence_score=0.0,
        )

def enrich_with_live_prices(
    trusted_candidates: list[dict], query: str, db: Session, offers: list[dict] | None = None
) -> list[dict]:
    """
    Takes trusted candidates (each already tagged with a `platform`) plus the
    generated text query, and returns enriched product dicts with live price,
    currency, rating, review_count, price_source, extraction_method and
    confidence_score filled in wherever available - and left as None, never
    fabricated, where not.

    Also appends any additional trusted-platform offers Google Shopping found
    that weren't already among the Lens candidates, so the price engine can
    surface options Lens alone missed.

    `offers` can be pre-fetched (see fetch_offers_for_query) and passed in to
    avoid re-querying; if omitted, this fetches them itself as before.
    """
    if offers is None:
        offers = fetch_offers_for_query(query, db)
    logger.info("Shopping Results Count: %d", len(offers))

    offers_by_platform = _group_offers_by_platform(offers)

    # PERF: run each candidate's extraction concurrently instead of one at
    # a time. _extract_price_for_candidate() is a blocking network call
    # (and, when Tiers 1-2 miss, a full headless-browser page render) with
    # no shared state between candidates - offers_by_platform is only ever
    # read, never written, by these workers, and each candidate's own dict
    # is independent. On a search with several trusted candidates this
    # turns "sum of every candidate's extraction time" into roughly "the
    # slowest single candidate's extraction time" (bounded by
    # settings.price_extraction_workers), which is the single biggest
    # search-latency win available here - previously a page needing the
    # slow headless-browser fallback tier serialized behind every other
    # candidate too, even though none of them depend on each other.
    # extractions[i] corresponds to trusted_candidates[i] - order is
    # preserved exactly as before, just computed in parallel.
    worker_count = max(1, min(settings.price_extraction_workers, len(trusted_candidates)))
    if worker_count > 1:
        with ThreadPoolExecutor(max_workers=worker_count) as pool:
            extractions = list(
                pool.map(lambda c: _extract_price_for_candidate(c, offers_by_platform), trusted_candidates)
            )
    else:
        extractions = [_extract_price_for_candidate(c, offers_by_platform) for c in trusted_candidates]

    enriched: list[dict] = []
    covered_platforms: set[str] = set()

    for candidate, extraction in zip(trusted_candidates, extractions):
        result = dict(candidate)
        platform = result["platform"]
        covered_platforms.add(platform)

        if extraction.price is not None:
            result["price"] = extraction.price
            result["currency"] = extraction.currency
        result["price_source"] = extraction.price_source
        result["extraction_method"] = extraction.extraction_method
        result["confidence_score"] = extraction.confidence_score

        platform_offers = offers_by_platform.get(platform, [])
        best_offer = _cheapest_offer(platform_offers)

        result["rating"] = extraction.rating
        result["review_count"] = extraction.review_count

        if result["rating"] is None:
            fallback_rating = best_offer.get("rating") if best_offer else candidate.get("rating")
            result["rating"] = normalize_rating(fallback_rating)
        if result["review_count"] is None:
            fallback_reviews = best_offer.get("reviews") if best_offer else candidate.get("reviews")
            result["review_count"] = normalize_review_count(fallback_reviews)

        enriched.append(result)

    for platform, platform_offers in offers_by_platform.items():
        if platform in covered_platforms:
            continue
        best_offer = _cheapest_offer(platform_offers)
        if best_offer is None:
            continue

        offer_title = best_offer.get("title") or query
        offer_link = best_offer["link"]
        if not match_trusted_platform(offer_link):
            # best_offer was only matched via source name - its link is a
            # Google-hosted page, not the retailer's. Send the user to a
            # real, working page on the correct platform instead.
            offer_link = build_platform_search_link(platform, offer_title) or offer_link

        enriched.append(
            {
                "platform": platform,
                "title": offer_title,
                "price": best_offer["price"],
                "currency": currency_resolver.resolve(
                    price_currency=best_offer.get("currency"),
                    price_text=str(best_offer.get("price")),
                    platform=platform,
                    url=best_offer["link"],
                ),
                "link": offer_link,
                "source_domain": platform,
                "thumbnail": best_offer.get("thumbnail"),
                "rating": normalize_rating(best_offer.get("rating")),
                "review_count": normalize_review_count(best_offer.get("reviews")),
                "price_source": "google_shopping",
                "extraction_method": "serpapi_google_shopping",
                "confidence_score": 0.95,
            }
        )
        logger.info("Price Extraction | platform=%s source=google_shopping (shopping-only match)", platform)

    return enriched

def _cheapest_offer(offers: list[dict]) -> dict | None:
    priced = [o for o in offers if extract_numeric_price(o.get("price")) is not None]
    if not priced:
        return None
    return min(priced, key=lambda o: extract_numeric_price(o["price"]))
