"""
Hybrid Search: one entry point supporting three modes - image only, text
only, image + text - with the last one genuinely blending visual
similarity and text relevance rather than just running one pipeline and
ignoring the other input.

  * Image only  -> delegates straight to search_service.process_image_search
    (untouched, byte-for-byte the same pipeline as before this module
    existed).
  * Text only   -> delegates to text_search_service.process_text_search
    (also untouched), with any budget phrase ("under 5000") parsed out and
    applied as a post-filter on the real results.
  * Image + text -> the new path (see _run_hybrid below): run the real,
    primary Google Lens/Shopping pipeline via
    search_service.process_image_search - exactly like a plain image
    search, including whatever capped/deduped internal-index
    recommendations that pipeline appends after Lens's own results (see
    search_service._supplement_with_internal_index) - then re-rank
    *everything* it returns with the Ranking Engine (see
    app/services/ranking/) using TextRelevanceSignal plus every other
    signal, with any budget parsed out applied as a hard pre-filter.
    Google Lens's results stay the trusted foundation of the response;
    the internal index, even post-rerank, is never more than a few extra
    suggestions riding along on top of it.

Nothing in app/services/text_search_service.py is modified to support this
- it remains independently callable exactly as before, and this module is
the only thing that combines it with the image pipeline.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from fastapi import BackgroundTasks
from sqlalchemy.orm import Session

from app.models import PurchaseLink, SearchResponse
from app.services import preferences_service, search_service, text_search_service
from app.services.hybrid_search.query_parser import ParsedTextQuery, parse_hybrid_text
from app.services.price_utils import extract_numeric_price
from app.services.product_index import service as product_index_service
from app.services.ranking import RankingContext, build_engine

logger = logging.getLogger(__name__)


class InvalidHybridSearchError(ValueError):
    """Raised when neither an image nor a text query was provided - the
    router translates this into a 400, same convention as every other
    validation error in the app."""


def process_hybrid_search(
    db: Session,
    *,
    image_bytes: bytes | None = None,
    filename: str | None = None,
    text_query: str | None = None,
    user_id: int | None = None,
    background_tasks: BackgroundTasks | None = None,
) -> SearchResponse:
    """The single entry point for all three search modes. Exactly one of
    the following happens:

      * both image_bytes and a non-empty text_query -> the hybrid path
      * only image_bytes                              -> plain image search
      * only text_query                                -> plain text search
      * neither                                        -> InvalidHybridSearchError

    `background_tasks`, when supplied by the caller (see
    app/routers/search.py), is forwarded to search_service.process_image_search
    for both the image-only path and the Lens-fallback half of the hybrid
    path, so the Product Index update for either one runs after the
    response is already on its way back, exactly like the plain
    POST /api/search/image endpoint - see process_image_search's own
    docstring. Optional and backward compatible: omitting it keeps
    indexing synchronous, exactly as before this parameter existed.
    """
    has_image = bool(image_bytes)
    parsed = parse_hybrid_text(text_query)
    has_text = bool(parsed.search_text) or parsed.budget_max is not None

    if not has_image and not has_text:
        raise InvalidHybridSearchError("Provide an image, a text query, or both.")

    if has_image and not has_text:
        response = search_service.process_image_search(
            image_bytes, filename or "upload.jpg", db, user_id=user_id, background_tasks=background_tasks
        )
        response.search_mode = "image"
        return response

    if has_text and not has_image:
        response = text_search_service.process_text_search(
            parsed.search_text or parsed.raw, db, query_source="hybrid_text", user_id=user_id
        )
        response = _apply_budget_filter(response, parsed.budget_max)
        response.search_mode = "text"
        return response

    return _run_hybrid(db, image_bytes, filename, parsed, user_id, background_tasks)


def _apply_budget_filter(response: SearchResponse, budget_max: float | None) -> SearchResponse:
    """Post-filters an already-complete SearchResponse's results by an
    explicit budget ("under 5000"). Applied after the fact (rather than
    threaded into text_search_service's own query-broadening logic) so
    that module stays untouched. Never returns zero results for a query
    that otherwise had matches - if the budget filter would empty the
    list, it's skipped and the response says so instead."""
    if budget_max is None or not response.results:
        return response

    within_budget = [
        link for link in response.results
        if (price := extract_numeric_price(link.price)) is None or price <= budget_max
    ]
    if within_budget:
        response.results = within_budget
        response.trusted_matches_returned = len(within_budget)
        response.priced_count = sum(1 for link in within_budget if link.price is not None)
        addition = f"Filtered to items at or under {budget_max:g}."
    else:
        addition = f"No results were at or under {budget_max:g}; showing all matches instead."
    response.note = f"{response.note} {addition}".strip() if response.note else addition
    return response


def _run_hybrid(
    db: Session,
    image_bytes: bytes,
    filename: str | None,
    parsed: ParsedTextQuery,
    user_id: int | None,
    background_tasks: BackgroundTasks | None = None,
) -> SearchResponse:
    """Google Lens (via search_service.process_image_search) is always the
    primary pipeline for the image half of a hybrid search - see this
    module's docstring. Its response (Lens results, plus any capped
    internal-index supplement that pipeline already appended) is then
    re-ranked by text relevance/budget below."""
    response = search_service.process_image_search(
        image_bytes, filename or "upload.jpg", db, user_id=user_id, background_tasks=background_tasks
    )
    return _rerank_lens_response(response, parsed)


@dataclass
class _PurchaseLinkCandidate:
    """Adapter making a PurchaseLink duck-type-compatible with
    RankingContext's candidate shape, so the same Ranking Engine used for
    the internal Product Index can also rank Google-Lens/Shopping-sourced
    results in the hybrid fallback path below - no separate scoring logic
    needed. Signals that need a field this adapter doesn't have
    (times_seen, created_at/updated_at - Lens results carry no such
    catalog stats) just see None and sit out, same as any other candidate
    missing that data.
    """

    link: PurchaseLink
    title: str | None
    brand: str | None
    category: str | None
    price: float | None
    rating: float | None
    review_count: int | None
    source: str | None
    times_seen: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


def _to_candidate(link: PurchaseLink) -> _PurchaseLinkCandidate:
    return _PurchaseLinkCandidate(
        link=link,
        title=link.title,
        brand=link.brand,
        category=preferences_service.categorize_text(link.title),
        price=extract_numeric_price(link.price),
        rating=link.rating,
        review_count=link.review_count,
        source=link.platform,
    )


def _rerank_lens_response(response: SearchResponse, parsed: ParsedTextQuery) -> SearchResponse:
    """Re-ranks an already-complete, Google-Lens-primary SearchResponse
    (Lens results plus any supplemental internal-index recommendations
    already appended by search_service.process_image_search) by text
    relevance, and applies the budget hard-filter. Brand/category/
    price-vs-query signals simply sit out here (there's no single "query
    product" for a bare image upload), leaving text_relevance, rating, and
    review_count to do the reordering.
    """
    response.search_mode = "hybrid"
    if not response.results or not (parsed.relevance_text or parsed.budget_max is not None):
        return response

    candidates = [_to_candidate(link) for link in response.results]
    max_reviews = max((c.review_count for c in candidates if c.review_count), default=0)

    engine = build_engine()
    contexts = [
        (
            candidate,
            RankingContext(
                candidate=candidate,
                query_text=parsed.relevance_text or None,
                reference_max_review_count=max_reviews,
            ),
        )
        for candidate in candidates
    ]
    ranked = engine.rank(contexts)

    if parsed.budget_max is not None:
        within_budget = [r for r in ranked if r.candidate.price is None or r.candidate.price <= parsed.budget_max]
        if within_budget:
            ranked = within_budget

    reordered: list[PurchaseLink] = []
    for result in ranked:
        link = result.candidate.link
        link.ranking_score = result.score.total_score
        link.ranking_summary = result.score.summary
        link.ranking_explanation = [
            product_index_service.to_ranking_contribution_schema(c) for c in result.score.contributions
        ]
        reordered.append(link)

    response.results = reordered
    response.trusted_matches_returned = len(reordered)
    response.priced_count = sum(1 for link in reordered if link.price is not None)

    addition = "Re-ranked by text relevance."
    if parsed.budget_max is not None:
        addition += f" Budget filter: at or under {parsed.budget_max:g}, where possible."
    response.note = f"{response.note} {addition}".strip() if response.note else addition
    return response
