"""
Orchestrates a full image search end-to-end. This is the only place that
knows the whole pipeline shape; app/routers/search.py just calls into this
module and translates the result into HTTP.

Pipeline:
  1. Hash the image; reuse a cached result if we've seen this exact photo
     recently (avoids duplicate Cloudinary + SerpApi calls).
  2. Google Lens/SerpApi is always the primary, trusted pipeline and
     always runs (unless step 1 already answered from cache):
     a. Upload to Cloudinary to get a public URL SerpApi's Lens engine can fetch.
     b. Google Lens search -> candidate purchase links.
     c. Filter candidates down to the trusted platform allowlist.
     d. Build a resilient product-search query from the Lens response.
     e. Resolve live prices for every trusted candidate (three-tier fallback).
     f. Normalize, dedupe, sort by price, mark the best deal.
  3. Only after Lens has answered: if settings.enable_internal_index_search,
     VisualFind's own Product Index (see
     app/services/product_index/service.py::search_by_image) is also
     checked and any matches - re-ranked by the multi-signal Ranking
     Engine, see app/services/ranking/ - are appended *after* Lens's
     results as supplemental "also in our catalog" recommendations (see
     _supplement_with_internal_index). The index is never allowed to
     answer a search on its own, replace Lens's results, or influence
     best-deal selection: its source/price data isn't reliable enough to
     be trusted outright, only to suggest extra options once Lens has
     already answered.
  4. Persist to search history + cache; feed Lens's own results back into
     the Product Index (new products get cataloged and embedded here -
     see _index_products) so it keeps growing for future supplemental
     recommendations; return the response.

Every external call is wrapped so a single failure (one retailer's page is
down, Shopping has no results, etc.) degrades gracefully instead of taking
the whole search down - partial results are always better than none.
"""

import hashlib
import json
import logging
import time

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SearchLog
from app.models import PriceHistoryComparison, PurchaseLink, SearchResponse
from app.services import cache_service, price_history_service, price_service, query_builder
from app.services.brand_resolution import BrandResolutionService, official_product_to_merge_dict
from app.services.domain_filter import match_trusted_platform
from app.services.indexing.runner import index_purchase_links_in_background
from app.services.product_index import service as product_index_service
from app.services.price_utils import (
    annotate_quick_commerce,
    dedupe_products,
    extract_numeric_price,
    guess_brand,
    mark_best_deal,
    normalize_merchant_name,
    pick_fastest_delivery,
)
from app.services.search_providers import SearchProviderError, get_provider

logger = logging.getLogger(__name__)

_brand_resolution_service = BrandResolutionService()

_PURCHASE_LINK_FIELDS = (
    "platform",
    "title",
    "price",
    "currency",
    "link",
    "source_domain",
    "thumbnail",
    "rating",
    "review_count",
    "price_source",
    "extraction_method",
    "confidence_score",
)

def _to_purchase_link(enriched: dict) -> PurchaseLink:
    data = {field: enriched.get(field) for field in _PURCHASE_LINK_FIELDS}
    data["platform"] = normalize_merchant_name(data.get("platform"))
    if not data.get("source_domain"):
        data["source_domain"] = data.get("platform")
    if data.get("price") is not None and not isinstance(data["price"], str):
        data["price"] = str(data["price"])
    data["brand"] = enriched.get("brand") or guess_brand(data.get("title"), data.get("platform"))
    return PurchaseLink(**data)

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

def _index_products(
    purchase_links: list[PurchaseLink], db: Session, background_tasks: BackgroundTasks | None = None
) -> None:
    """Feeds this search's results into the internal Product Index via the
    Indexing Pipeline (see app/services/indexing/) - building a real
    catalog instead of throwing search results away once the response is
    sent.

    When `background_tasks` is provided (the normal case - see
    app/routers/search.py), indexing is scheduled to run *after* the HTTP
    response has already been sent, on its own database session (see
    app.services.indexing.runner.index_purchase_links_in_background) - the
    person doesn't wait on catalog bookkeeping to get their search
    results. Without it (e.g. direct/test calls to process_image_search
    that don't wire up BackgroundTasks), indexing runs inline using the
    request's own session, exactly as before.

    Never allowed to break or slow down the search response beyond its own
    internal per-search caps, so any failure here is logged and swallowed
    rather than raised.
    """
    if background_tasks is not None:
        background_tasks.add_task(index_purchase_links_in_background, purchase_links)
        return
    try:
        product_index_service.index_purchase_links(db, purchase_links)
    except Exception:
        logger.exception("Product Index update failed (non-fatal, search result is unaffected)")

def _build_note(total_candidates: int, trusted_count: int, priced_count: int) -> str | None:
    if total_candidates == 0:
        return "No visual matches found. Try uploading a clearer image of the product."
    if trusted_count == 0:
        return "SerpAPI found visual matches, but none were from trusted shopping platforms."
    if priced_count == 0:
        return "Trusted products were found, but live prices could not be retrieved for any of them right now."
    return None

def _result_key(link: PurchaseLink) -> tuple[str, str]:
    """Loose de-dupe key so an internal-index recommendation that's
    actually the same product Lens already returned doesn't get listed
    twice."""
    return (
        (link.title or "").strip().lower(),
        (link.source_domain or link.platform or "").strip().lower(),
    )

def _supplement_with_internal_index(
    db: Session, file_bytes: bytes, primary_links: list[PurchaseLink], user_id: int | None = None
) -> list[PurchaseLink]:
    """Appends a capped, deduped set of VisualFind's own Product Index
    matches *after* Google Lens's already-complete, primary results - see
    this module's docstring for why the index is never allowed to answer
    a search on its own. Only called once Lens has already produced
    `primary_links`; never raises (any failure here is logged and
    swallowed, exactly like every other best-effort enrichment step in
    this pipeline) since a broken supplemental lookup should never take
    down a search that Lens already answered successfully.
    """
    try:
        internal_matches = product_index_service.search_by_image(db, file_bytes)
    except Exception:
        logger.exception("Internal index lookup failed (non-fatal); returning Google Lens results only")
        return []
    if len(internal_matches) < settings.product_index_search_min_matches:
        return []

    ranked = product_index_service.rank_matches(db, internal_matches, user_id=user_id)
    existing_keys = {_result_key(link) for link in primary_links}

    supplemental: list[PurchaseLink] = []
    for ranked_product in ranked:
        candidate_link = product_index_service.ranked_product_to_purchase_link(ranked_product)
        key = _result_key(candidate_link)
        if key in existing_keys:
            continue
        existing_keys.add(key)
        supplemental.append(candidate_link)
        if len(supplemental) >= settings.internal_index_max_supplemental_results:
            break

    if supplemental:
        logger.info(
            "Internal Index Supplement | added=%d additional recommendation(s) after Google Lens (primary)",
            len(supplemental),
        )
    return supplemental

def process_image_search(
    file_bytes: bytes,
    filename: str,
    db: Session,
    user_id: int | None = None,
    background_tasks: BackgroundTasks | None = None,
) -> SearchResponse:
    """`background_tasks`, when supplied by the caller (see
    app/routers/search.py), lets this search's Product Index update run
    asynchronously - scheduled to execute after the response is already on
    its way back to the person, on its own DB session, instead of adding
    Product Index bookkeeping to the search's own latency. Optional and
    backward compatible: omitting it (as every existing test/caller does)
    keeps indexing synchronous, on this same `db` session, exactly as
    before.
    """
    start = time.perf_counter()

    image_hash = hashlib.sha256(file_bytes).hexdigest()
    logger.info("Image Uploaded | filename=%s size_kb=%.1f hash=%s", filename, len(file_bytes) / 1024, image_hash[:12])

    cache_key = f"image_result:{image_hash}"
    cached = cache_service.get_cached(db, cache_key)
    if cached is not None:
        logger.info("Reusing cached result for previously-searched image (hash=%s)", image_hash[:12])
        return _build_response_from_cache(cached, db, image_hash, user_id=user_id, background_tasks=background_tasks)

    provider = get_provider()
    try:
        identify_result = provider.identify(file_bytes, filename)
    except SearchProviderError as e:
        logger.error("Search provider '%s' failed: %s", provider.name, e)
        raise

    candidates = identify_result.candidates
    best_guess = identify_result.best_guess
    # Kept as `lens_response` downstream (query_builder, brand_resolution)
    # since those modules degrade gracefully to candidate-based heuristics
    # when this doesn't have Lens-shaped keys (knowledge_graph,
    # search_information) - see ProviderIdentifyResult.raw_response's
    # docstring. It's the active provider's raw payload, {} for a provider
    # that doesn't have one, not necessarily an actual Lens response.
    lens_response = identify_result.raw_response
    logger.info(
        "Provider Query | provider=%s best_guess=%s candidates=%d",
        provider.name, best_guess, len(candidates),
    )

    trusted_candidates = []
    for candidate in candidates:
        platform = match_trusted_platform(candidate["link"])
        if platform is None:
            continue
        trusted_candidates.append({**candidate, "platform": platform})

    query, query_source = query_builder.build_product_query(lens_response, candidates)
    logger.info("Shopping Query | query=%s source=%s", query, query_source)

    offers = price_service.fetch_offers_for_query(query, db)

    brand_result = _brand_resolution_service.resolve(
        lens_response=lens_response, candidates=candidates, query=query, offers=offers
    )

    enriched = price_service.enrich_with_live_prices(trusted_candidates, query, db, offers=offers)

    if brand_result.official_product is not None:
        enriched.append(
            official_product_to_merge_dict(brand_result.official_product, brand_result.detected_brand)
        )

    enriched = dedupe_products(enriched)

    purchase_links = [_to_purchase_link(item) for item in enriched]
    purchase_links = mark_best_deal(purchase_links)
    purchase_links = annotate_quick_commerce(purchase_links)
    fastest_delivery = pick_fastest_delivery(purchase_links)

    best_deal = next((link for link in purchase_links if link.is_best_deal), None)

    # Feed only Lens's own (primary, trusted) results into the Product
    # Index for future cataloging - re-indexing supplemental matches that
    # already came *from* the index would be redundant.
    _index_products(purchase_links, db, background_tasks)

    supplemental_links: list[PurchaseLink] = []
    if settings.enable_internal_index_search:
        supplemental_links = _supplement_with_internal_index(db, file_bytes, purchase_links, user_id=user_id)
        if supplemental_links:
            purchase_links = purchase_links + supplemental_links

    priced_count = sum(1 for link in purchase_links if link.price is not None)

    execution_time_ms = int((time.perf_counter() - start) * 1000)
    logger.info("Sorting | %d priced of %d trusted results", priced_count, len(purchase_links))
    logger.info("Best Deal | %s", f"{best_deal.platform} @ {best_deal.price}" if best_deal else "none")
    logger.info("Execution Time | %d ms", execution_time_ms)

    note = _build_note(len(candidates), len(trusted_candidates), priced_count)
    if supplemental_links:
        supplement_note = (
            f"Also including {len(supplemental_links)} recommendation(s) from VisualFind's own index."
        )
        note = f"{note} {supplement_note}".strip() if note else supplement_note
    price_history = _track_price_history(db, best_deal, user_id)

    log_entry = SearchLog(
        user_id=user_id,
        image_filename=filename,
        image_hash=image_hash,
        product_query=query,
        query_source=f"{query_source}+index_supplement" if supplemental_links else query_source,
        best_guess_label=best_guess,
        result_count=len(candidates),
        filtered_count=len(trusted_candidates) + len(supplemental_links),
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
            "best_guess_label": best_guess,
            "product_query": query,
            "total_matches_found": len(candidates),
            "trusted_matches_returned": len(trusted_candidates) + len(supplemental_links),
            "priced_count": priced_count,
            "results": [link.model_dump() for link in purchase_links],
            "note": note,
            "detected_brand": brand_result.detected_brand,
            "brand_confidence": brand_result.brand_confidence,
            "official_domain": brand_result.official_domain,
            "official_product_found": brand_result.official_product is not None,
        },
    )

    return SearchResponse(
        search_id=log_entry.id,
        best_guess_label=best_guess,
        product_query=query,
        total_matches_found=len(candidates),
        trusted_matches_returned=len(trusted_candidates) + len(supplemental_links),
        priced_count=priced_count,
        detected_brand=brand_result.detected_brand,
        brand_confidence=brand_result.brand_confidence,
        official_domain=brand_result.official_domain,
        official_product_found=brand_result.official_product is not None,
        execution_time_ms=execution_time_ms,
        from_cache=False,
        results=purchase_links,
        note=note,
        price_history=price_history,
        fastest_delivery=fastest_delivery,
    )

def _build_response_from_cache(
    cached: dict,
    db: Session,
    image_hash: str,
    user_id: int | None = None,
    background_tasks: BackgroundTasks | None = None,
) -> SearchResponse:
    """
    Still writes a SearchLog row (so history reflects that a search happened),
    but skips every external API call.
    """
    purchase_links = [PurchaseLink(**item) for item in cached.get("results", [])]
    purchase_links = annotate_quick_commerce(purchase_links)
    fastest_delivery = pick_fastest_delivery(purchase_links)
    best_deal = next((link for link in purchase_links if link.is_best_deal), None)
    price_history = _track_price_history(db, best_deal, user_id)

    _index_products(purchase_links, db, background_tasks)

    log_entry = SearchLog(
        user_id=user_id,
        image_filename=f"cached-{image_hash[:12]}",
        image_hash=image_hash,
        product_query=cached.get("product_query"),
        query_source="cache",
        best_guess_label=cached.get("best_guess_label"),
        result_count=cached.get("total_matches_found", 0),
        filtered_count=cached.get("trusted_matches_returned", 0),
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
        best_guess_label=cached.get("best_guess_label"),
        product_query=cached.get("product_query"),
        total_matches_found=cached.get("total_matches_found", 0),
        trusted_matches_returned=cached.get("trusted_matches_returned", 0),
        priced_count=cached.get("priced_count", 0),
        detected_brand=cached.get("detected_brand"),
        brand_confidence=cached.get("brand_confidence"),
        official_domain=cached.get("official_domain"),
        official_product_found=bool(cached.get("official_product_found")),
        execution_time_ms=0,
        from_cache=True,
        results=purchase_links,
        note=cached.get("note"),
        price_history=price_history,
        fastest_delivery=fastest_delivery,
    )
