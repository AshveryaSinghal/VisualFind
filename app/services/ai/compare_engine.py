"""
Powers the 'Compare Products' feature: given exactly two REAL products
(already found by the search pipeline) plus a short user preference
questionnaire, produce a personalized winner + explanation.

Design mirrors recommendation_engine.py's safety model:
- Gemini never sees or invents a product; it only ever returns an index
  (0 or 1) into the two products we send it.
- Numeric value/price/rating/review scores are computed deterministically
  in this file from the real PurchaseLink data - Gemini is only asked to
  narrate/explain, never to invent numbers.
- If Gemini is unavailable or misbehaves, a deterministic fallback still
  returns a sensible, personalized-as-possible answer instead of failing
  the whole request.
"""

import logging
from dataclasses import dataclass

from app.models import (
    ComparePriority,
    ProductValueScore,
    PurchaseLink,
    SmartCompareRequest,
    SmartCompareResponse,
)
from app.services.ai import gemini_service
from app.services.ai.prompt_builder import (
    COMPARE_RESPONSE_SCHEMA,
    COMPARE_SYSTEM_INSTRUCTION,
    build_compare_user_prompt,
)
from app.services.price_utils import extract_numeric_price

logger = logging.getLogger(__name__)

def compare(request: SmartCompareRequest) -> SmartCompareResponse:
    a, b = request.product_a, request.product_b

    scores_a, scores_b = _compute_value_scores(a, b, request.priority)

    try:
        raw = gemini_service.generate_json(
            system_instruction=COMPARE_SYSTEM_INSTRUCTION,
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": build_compare_user_prompt(
                                _preferences_text(request),
                                [_to_compare_dict(a, 0), _to_compare_dict(b, 1)],
                                [
                                    {"index": 0, **scores_a.model_dump()},
                                    {"index": 1, **scores_b.model_dump()},
                                ],
                            )
                        }
                    ],
                }
            ],
            response_schema=COMPARE_RESPONSE_SCHEMA,
            temperature=0.3,
        )
    except gemini_service.GeminiError as e:
        logger.warning("Compare engine falling back to deterministic verdict: %s", e)
        return _fallback_compare(request, scores_a, scores_b)

    winner_index = raw.get("winner_index")
    if winner_index not in (0, 1):
        logger.warning("Gemini returned invalid winner_index=%r for compare; falling back", winner_index)
        return _fallback_compare(request, scores_a, scores_b)

    return SmartCompareResponse(
        winner_index=winner_index,
        headline=(raw.get("headline") or "").strip() or _default_headline(winner_index),
        personalized_reason=(raw.get("personalized_reason") or "").strip()
        or _default_reason(request, winner_index),
        price_verdict=(raw.get("price_verdict") or "").strip() or "Price comparison unavailable.",
        quality_verdict=(raw.get("quality_verdict") or "").strip()
        or "Quality comparison unavailable.",
        value_verdict=(raw.get("value_verdict") or "").strip() or "Value comparison unavailable.",
        feature_highlights_a=[str(f) for f in (raw.get("feature_highlights_a") or [])][:4],
        feature_highlights_b=[str(f) for f in (raw.get("feature_highlights_b") or [])][:4],
        value_scores_a=scores_a,
        value_scores_b=scores_b,
        confidence=_clamp01(raw.get("confidence")),
        used_ai=True,
    )

def _preferences_text(request: SmartCompareRequest) -> str:
    lines = []
    if request.budget:
        lines.append(f"- Budget: {request.budget} {request.budget_currency or 'INR'}")
    else:
        lines.append("- Budget: not specified")
    lines.append(f"- Main purpose: {request.main_purpose}")
    lines.append(f"- Preferred brand: {request.preferred_brand or 'no preference'}")
    lines.append(
        "- Priority: "
        + ("price (wants the cheaper/best-deal option)" if request.priority == ComparePriority.PRICE
           else "quality (wants the better-rated/more reliable option, even if pricier)")
    )
    lines.append(f"- Special preferences: {request.special_preferences or 'none given'}")
    return "\n".join(lines)

def _to_compare_dict(link: PurchaseLink, index: int) -> dict:
    return {
        "index": index,
        "title": link.title,
        "platform": link.platform,
        "brand": link.brand,
        "price": link.price,
        "currency": link.currency,
        "rating": link.rating,
        "review_count": link.review_count,
        "source_domain": link.source_domain,
        "is_official_store": "official" in (link.platform or "").lower(),
    }

def _compute_value_scores(
    a: PurchaseLink, b: PurchaseLink, priority: ComparePriority
) -> tuple[ProductValueScore, ProductValueScore]:
    """
    Deterministic, explainable 0-100 scores relative to the OTHER product in
    this specific comparison - never absolute, never AI-generated. This is
    what drives the comparison charts in the UI.
    """
    price_a = extract_numeric_price(a.price)
    price_b = extract_numeric_price(b.price)
    rating_a = a.rating if a.rating is not None else 0.0
    rating_b = b.rating if b.rating is not None else 0.0
    reviews_a = a.review_count if a.review_count is not None else 0
    reviews_b = b.review_count if b.review_count is not None else 0

    price_score_a, price_score_b = _relative_scores(price_a, price_b, lower_is_better=True)
    rating_score_a, rating_score_b = _relative_scores(rating_a, rating_b, lower_is_better=False)
    reviews_score_a, reviews_score_b = _relative_scores(reviews_a, reviews_b, lower_is_better=False)

    if priority == ComparePriority.PRICE:
        weights = (0.5, 0.3, 0.2)
    else:
        weights = (0.2, 0.55, 0.25)

    overall_a = (
        price_score_a * weights[0] + rating_score_a * weights[1] + reviews_score_a * weights[2]
    )
    overall_b = (
        price_score_b * weights[0] + rating_score_b * weights[1] + reviews_score_b * weights[2]
    )

    return (
        ProductValueScore(
            price_score=round(price_score_a, 1),
            rating_score=round(rating_score_a, 1),
            reviews_score=round(reviews_score_a, 1),
            overall_value_score=round(overall_a, 1),
        ),
        ProductValueScore(
            price_score=round(price_score_b, 1),
            rating_score=round(rating_score_b, 1),
            reviews_score=round(reviews_score_b, 1),
            overall_value_score=round(overall_b, 1),
        ),
    )

def _relative_scores(x, y, lower_is_better: bool) -> tuple[float, float]:
    if x is None and y is None:
        return 50.0, 50.0
    x = x if x is not None else 0
    y = y if y is not None else 0
    if x == y:
        return 50.0, 50.0

    lo, hi = min(x, y), max(x, y)
    span = hi - lo

    def scale(v: float) -> float:
        pct = (v - lo) / span * 100
        return 100 - pct if lower_is_better else pct

    return scale(x), scale(y)

def _clamp01(value) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    return max(0.0, min(1.0, float(value)))

def _default_headline(winner_index: int) -> str:
    return "Product A is the better pick" if winner_index == 0 else "Product B is the better pick"

def _default_reason(request: SmartCompareRequest, winner_index: int) -> str:
    winner = "the first product" if winner_index == 0 else "the second product"
    return (
        f"Based on your budget, your main purpose ({request.main_purpose}), and whether "
        f"price or quality mattered more to you, {winner} came out ahead on the numbers we "
        "could compare."
    )

@dataclass
class _FallbackPick:
    index: int
    scores: ProductValueScore

def _fallback_compare(
    request: SmartCompareRequest, scores_a: ProductValueScore, scores_b: ProductValueScore
) -> SmartCompareResponse:
    """
    Used only if the Gemini call fails outright (network/quota/not
    configured). Picks the product with the higher deterministic overall
    value score (already weighted by the user's stated price/quality
    priority) rather than fabricating an AI explanation.
    """
    winner_index = 0 if scores_a.overall_value_score >= scores_b.overall_value_score else 1
    a_title = request.product_a.title
    b_title = request.product_b.title
    winner_title = a_title if winner_index == 0 else b_title

    priority_text = (
        "since you said price matters more to you" if request.priority == ComparePriority.PRICE
        else "since you said quality matters more to you"
    )

    reason = (
        f"For your purpose ({request.main_purpose}), \"{winner_title}\" scores higher "
        f"once price, rating, and review count are weighed the way you asked ({priority_text}). "
        "The AI explanation service is temporarily unavailable, so this pick is based on the "
        "real price/rating/review numbers rather than a written explanation."
    )

    return SmartCompareResponse(
        winner_index=winner_index,
        headline=_default_headline(winner_index),
        personalized_reason=reason,
        price_verdict="Lower price wins on this metric." if request.priority == ComparePriority.PRICE
        else "Price compared, but you said quality matters more.",
        quality_verdict="Higher rating and review count indicate more reliable satisfaction.",
        value_verdict="Overall value score favors "
        + ("the first product." if winner_index == 0 else "the second product."),
        feature_highlights_a=[],
        feature_highlights_b=[],
        value_scores_a=scores_a,
        value_scores_b=scores_b,
        confidence=None,
        used_ai=False,
    )
