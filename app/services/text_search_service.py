"""
Runs a search from a plain-text query (produced either by the AI Shopping
Assistant or typed directly into the smart search bar) instead of an
uploaded image.

This is an ADDITIVE sibling to search_service.process_image_search - it
does not modify that function or anything it depends on. It reuses the same
trusted-platform pricing engine (app/services/price_service.py) so results
carry the same real prices, ratings, and dedupe/best-deal logic as image
search; it simply skips the Cloudinary/Google-Lens steps and starts
directly from a text query.
"""

import json
import logging
import time

from sqlalchemy.orm import Session

from app.database import SearchLog
from app.models import PriceHistoryComparison, PurchaseLink, SearchResponse
from app.services import cache_service, price_history_service, price_service
from app.services.brand_resolution import BrandResolutionResult, BrandResolutionService, official_product_to_merge_dict
from app.services.price_utils import (
    annotate_quick_commerce,
    dedupe_products,
    extract_numeric_price,
    guess_brand,
    mark_best_deal,
    pick_fastest_delivery,
)
from app.services.query_broadening import broaden_query
from app.services.search_service import _to_purchase_link

logger = logging.getLogger(__name__)

_brand_resolution_service = BrandResolutionService()

def _build_note(trusted_count: int, priced_count: int, is_exact_match: bool = True, fallback_query: str | None = None) -> str | None:
    if not is_exact_match and trusted_count > 0:
        return (
            f'No trusted-platform matches for the exact product. Showing the closest '
            f'alternatives for "{fallback_query}" instead.'
        )
    if trusted_count == 0:
        return "No trusted-platform matches were found for this search, even after broadening it. Try different wording."
    if priced_count == 0:
        return "Matches were found, but live prices could not be retrieved for any of them right now."
    return None

def _run_offer_search(query: str, db: Session) -> tuple[list[PurchaseLink], BrandResolutionResult]:
    """Runs the real search pipeline for one query string and returns
    normalized, deduped, best-deal-marked purchase links plus the brand
    resolution outcome for that query. Pure helper so the exact-match
    attempt and every broadened fallback attempt share identical logic - no
    separate/looser code path for alternatives.

    Text search has no Google Lens response/candidates (there's no image),
    so brand detection here leans on the query text itself and the Google
    Shopping merchant names in `offers` - see BrandDetector._from_titles and
    ._from_shopping_offers. That's enough signal for a known brand name
    (e.g. "plum face wash") to resolve confidently.
    """
    offers = price_service.fetch_offers_for_query(query, db)

    brand_result = _brand_resolution_service.resolve(
        lens_response={}, candidates=[], query=query, offers=offers
    )

    enriched = price_service.enrich_with_live_prices([], query, db, offers=offers)

    if brand_result.official_product is not None:
        enriched.append(
            official_product_to_merge_dict(brand_result.official_product, brand_result.detected_brand)
        )

    enriched = dedupe_products(enriched)
    purchase_links = [_to_purchase_link(item) for item in enriched]
    for link in purchase_links:
        if not link.brand:
            link.brand = guess_brand(link.title, link.platform)
    purchase_links = mark_best_deal(purchase_links)
    purchase_links = annotate_quick_commerce(purchase_links)
    return purchase_links, brand_result

def process_text_search(
    query: str, db: Session, query_source: str = "text", user_id: int | None = None
) -> SearchResponse:
    """
    query_source distinguishes AI-assistant-generated queries ("ai_chat")
    from directly-typed smart-search-bar queries ("text") in search history/
    analytics, without touching the SearchLog schema.
    """
    start = time.perf_counter()
    query = query.strip()

    cache_key = f"text_search_result:{query.lower()}"
    cached = cache_service.get_cached(db, cache_key)
    if cached is not None:
        logger.info("Reusing cached text-search result for query=%s", query)
        return _build_response_from_cache(cached, db, query, query_source, user_id=user_id)

    purchase_links, brand_result = _run_offer_search(query, db)
    is_exact_match = True
    fallback_query: str | None = None
    effective_query = query

    if not purchase_links:
        for candidate_query in broaden_query(query):
            candidate_links, candidate_brand_result = _run_offer_search(candidate_query, db)
            if candidate_links:
                purchase_links = candidate_links
                brand_result = candidate_brand_result
                is_exact_match = False
                fallback_query = candidate_query
                effective_query = candidate_query
                logger.info(
                    "No exact match for query=%r; broadened to %r and found %d result(s)",
                    query, candidate_query, len(candidate_links),
                )
                break

    priced_count = sum(1 for link in purchase_links if link.price is not None)
    best_deal = next((link for link in purchase_links if link.is_best_deal), None)
    fastest_delivery = pick_fastest_delivery(purchase_links)

    execution_time_ms = int((time.perf_counter() - start) * 1000)
    note = _build_note(len(purchase_links), priced_count, is_exact_match, fallback_query)

    price_history = _track_price_history(db, best_deal, user_id)

    log_entry = SearchLog(
        user_id=user_id,
        image_filename=f"text-search:{query[:80]}",
        image_hash=None,
        product_query=effective_query,
        query_source=query_source,
        best_guess_label=query,
        result_count=len(purchase_links),
        filtered_count=len(purchase_links),
        priced_count=priced_count,
        best_deal_platform=best_deal.platform if best_deal else None,
        best_deal_price=extract_numeric_price(best_deal.price) if best_deal else None,
        execution_time_ms=execution_time_ms,
        results_json=json.dumps([link.model_dump() for link in purchase_links]),
        detected_brand=brand_result.detected_brand,
        brand_confidence=brand_result.brand_confidence,
        official_domain=brand_result.official_domain,
        official_product_found=1 if brand_result.official_product is not None else 0,
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)

    cache_service.set_cached(
        db,
        cache_key,
        {
            "product_query": query,
            "priced_count": priced_count,
            "results": [link.model_dump() for link in purchase_links],
            "note": note,
            "is_exact_match": is_exact_match,
            "fallback_query": fallback_query,
            "detected_brand": brand_result.detected_brand,
            "brand_confidence": brand_result.brand_confidence,
            "official_domain": brand_result.official_domain,
            "official_product_found": brand_result.official_product is not None,
        },
    )

    return SearchResponse(
        search_id=log_entry.id,
        best_guess_label=query,
        product_query=effective_query,
        total_matches_found=len(purchase_links),
        trusted_matches_returned=len(purchase_links),
        priced_count=priced_count,
        detected_brand=brand_result.detected_brand,
        brand_confidence=brand_result.brand_confidence,
        official_domain=brand_result.official_domain,
        official_product_found=brand_result.official_product is not None,
        execution_time_ms=execution_time_ms,
        from_cache=False,
        results=purchase_links,
        note=note,
        is_exact_match=is_exact_match,
        fallback_query=fallback_query,
        price_history=price_history,
        fastest_delivery=fastest_delivery,
    )

def _track_price_history(db: Session, best_deal: PurchaseLink | None, user_id: int | None) -> PriceHistoryComparison | None:
    if best_deal is None:
        return None
    price = extract_numeric_price(best_deal.price)
    if price is None:
        return None
    return price_history_service.record_and_compare(
        db,
        product_name=best_deal.title,
        marketplace=best_deal.platform,
        price=price,
        currency=best_deal.currency,
        user_id=user_id,
    )

def _build_response_from_cache(
    cached: dict, db: Session, query: str, query_source: str, user_id: int | None = None
) -> SearchResponse:
    purchase_links = [PurchaseLink(**item) for item in cached.get("results", [])]
    purchase_links = annotate_quick_commerce(purchase_links)
    fastest_delivery = pick_fastest_delivery(purchase_links)
    best_deal = next((link for link in purchase_links if link.is_best_deal), None)
    is_exact_match = cached.get("is_exact_match", True)
    fallback_query = cached.get("fallback_query")
    price_history = _track_price_history(db, best_deal, user_id)

    log_entry = SearchLog(
        user_id=user_id,
        image_filename=f"text-search-cached:{query[:70]}",
        image_hash=None,
        product_query=query,
        query_source=f"{query_source}_cache",
        best_guess_label=query,
        result_count=len(purchase_links),
        filtered_count=len(purchase_links),
        priced_count=cached.get("priced_count", 0),
        best_deal_platform=best_deal.platform if best_deal else None,
        best_deal_price=extract_numeric_price(best_deal.price) if best_deal else None,
        execution_time_ms=0,
        results_json=json.dumps(cached.get("results", [])),
        detected_brand=cached.get("detected_brand"),
        brand_confidence=cached.get("brand_confidence"),
        official_domain=cached.get("official_domain"),
        official_product_found=1 if cached.get("official_product_found") else 0,
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)

    return SearchResponse(
        search_id=log_entry.id,
        best_guess_label=query,
        product_query=query,
        total_matches_found=len(purchase_links),
        trusted_matches_returned=len(purchase_links),
        priced_count=cached.get("priced_count", 0),
        detected_brand=cached.get("detected_brand"),
        brand_confidence=cached.get("brand_confidence"),
        official_domain=cached.get("official_domain"),
        official_product_found=bool(cached.get("official_product_found")),
        execution_time_ms=0,
        from_cache=True,
        results=purchase_links,
        note=cached.get("note"),
        is_exact_match=is_exact_match,
        fallback_query=fallback_query,
        price_history=price_history,
        fastest_delivery=fastest_delivery,
    )
