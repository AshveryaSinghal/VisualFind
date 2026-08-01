"""
Second Gemini call in the pipeline: given the REAL products the existing
search pipeline (search_service / text_search_service) already found -
real prices, real ratings, real purchase links - ask Gemini to compare them
and recommend one.

Structural safety: Gemini never sees or invents a product. It only ever
returns an *index* into the list we sent it. If that index is out of range,
missing, or the list is empty, we simply have no recommendation - we never
fall back to a fabricated one.
"""

import logging
from dataclasses import dataclass, field

from app.models import PurchaseLink
from app.services.ai import gemini_service
from app.services.ai.prompt_builder import (
    RECOMMENDATION_RESPONSE_SCHEMA,
    RECOMMENDATION_SYSTEM_INSTRUCTION,
    build_recommendation_user_prompt,
)
from app.services.price_utils import extract_numeric_price

logger = logging.getLogger(__name__)

@dataclass
class RecommendationResult:
    recommended: PurchaseLink | None
    reason: str | None
    why_it_matches: str | None
    alternatives: list[PurchaseLink] = field(default_factory=list)
    money_saved: float | None = None

def recommend(
    purchase_links: list[PurchaseLink],
    requirements_summary: str,
    budget_max: float | None,
) -> RecommendationResult:
    priced_links = [link for link in purchase_links if link.price is not None]
    candidates = priced_links or purchase_links

    if not candidates:
        return RecommendationResult(recommended=None, reason=None, why_it_matches=None)

    indexed_products = [_to_ranking_dict(link, i) for i, link in enumerate(candidates)]

    try:
        raw = gemini_service.generate_json(
            system_instruction=RECOMMENDATION_SYSTEM_INSTRUCTION,
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": build_recommendation_user_prompt(
                                requirements_summary, indexed_products
                            )
                        }
                    ],
                }
            ],
            response_schema=RECOMMENDATION_RESPONSE_SCHEMA,
            temperature=0.2,
        )
    except gemini_service.GeminiError as e:
        logger.warning("Recommendation engine falling back to cheapest match: %s", e)
        return _fallback_recommendation(candidates, budget_max)

    recommended_index = raw.get("recommended_index")
    if not isinstance(recommended_index, int) or not (0 <= recommended_index < len(candidates)):
        logger.warning("Gemini returned out-of-range recommended_index=%r; falling back", recommended_index)
        return _fallback_recommendation(candidates, budget_max)

    recommended = candidates[recommended_index]

    alt_indices = raw.get("alternative_indices") or []
    alternatives = [
        candidates[i]
        for i in alt_indices
        if isinstance(i, int) and 0 <= i < len(candidates) and i != recommended_index
    ][:3]

    money_saved = _compute_money_saved(recommended, candidates)

    return RecommendationResult(
        recommended=recommended,
        reason=(raw.get("reason") or "").strip() or None,
        why_it_matches=(raw.get("why_it_matches") or "").strip() or None,
        alternatives=alternatives,
        money_saved=money_saved,
    )

def _fallback_recommendation(
    candidates: list[PurchaseLink], budget_max: float | None
) -> RecommendationResult:
    """
    Used only if Gemini's ranking call fails outright (network/quota/etc).
    Never fabricates a product - just applies a deterministic, defensible
    rule (cheapest priced option within budget, else cheapest overall) over
    the same real candidate list.
    """
    priced = [
        (link, extract_numeric_price(link.price))
        for link in candidates
        if extract_numeric_price(link.price) is not None
    ]
    if not priced:
        recommended = candidates[0]
        return RecommendationResult(
            recommended=recommended,
            reason="Best available match for your search.",
            why_it_matches=None,
        )

    if budget_max:
        in_budget = [(link, price) for link, price in priced if price <= budget_max]
        pool = in_budget or priced
    else:
        pool = priced

    pool.sort(key=lambda pair: pair[1])
    recommended, _ = pool[0]
    alternatives = [link for link, _ in pool[1:4] if link is not recommended]

    money_saved = _compute_money_saved(recommended, candidates)

    return RecommendationResult(
        recommended=recommended,
        reason="Lowest price among matching, trusted-platform results.",
        why_it_matches="Fits within your stated budget." if budget_max else None,
        alternatives=alternatives,
        money_saved=money_saved,
    )

def _compute_money_saved(recommended: PurchaseLink, candidates: list[PurchaseLink]) -> float | None:
    recommended_price = extract_numeric_price(recommended.price)
    if recommended_price is None:
        return None
    other_prices = [
        p
        for link in candidates
        if link is not recommended and (p := extract_numeric_price(link.price)) is not None
    ]
    if not other_prices:
        return None
    highest = max(other_prices)
    saved = highest - recommended_price
    return round(saved, 2) if saved > 0 else None

def _to_ranking_dict(link: PurchaseLink, index: int) -> dict:
    return {
        "index": index,
        "title": link.title,
        "platform": link.platform,
        "price": link.price,
        "currency": link.currency,
        "rating": link.rating,
        "review_count": link.review_count,
        "is_official_store": "official" in (link.platform or "").lower(),
    }
