"""
Tier 5 - Validation.

Rejects numeric values that parsed fine but obviously aren't a real product
selling price: zero/one-rupee placeholders, absurd sentinel values, negative
numbers, and prices whose *role* marks them as something other than the
selling price (shipping, EMI, discount %, coupon amount) - those are caught
even earlier by keyword sniffing on the label/context, before we ever get to
the numeric check.

Pure function, no I/O - trivially unit-testable and safe to call for every
candidate without risk of raising.
"""

import re

from app.services.price_extraction.types import NormalizedCandidate, PriceRole

_INVALID_EXACT_VALUES = {0, 1}

_MAX_PLAUSIBLE_PRICE = 100_000_000

_MIN_PLAUSIBLE_PRICE = 2

_ROLE_KEYWORDS: dict[PriceRole, tuple[str, ...]] = {
    PriceRole.SHIPPING: ("shipping", "delivery fee", "delivery charge", "freight"),
    PriceRole.EMI_INSTALLMENT: ("emi", "installment", "instalment", "/mo", "per month", "monthly"),
    PriceRole.DISCOUNT_PERCENT: ("% off", "percent off", "discount", "you save"),
    PriceRole.COUPON: ("coupon", "promo code", "voucher"),
    PriceRole.LIST_PRICE: ("mrp", "was", "list price", "original price", "strike", "compare at"),
}

def infer_role_from_text(label: str | None, context: str | None) -> PriceRole:
    """
    Best-effort keyword sniff over a candidate's label/context to classify
    what kind of price this is. Falls back to UNKNOWN (treated as a
    plausible selling-price candidate) rather than guessing wrongly.
    """
    haystack = f"{label or ''} {context or ''}".lower()
    if not haystack.strip():
        return PriceRole.UNKNOWN

    for role, keywords in _ROLE_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            return role

    if re.search(r"%\s*(off|discount)", haystack):
        return PriceRole.DISCOUNT_PERCENT

    return PriceRole.UNKNOWN

def is_plausible_amount(value: float) -> bool:
    """Numeric sanity check only - role filtering happens separately."""
    if value is None:
        return False
    if value != value:
        return False
    if value < 0:
        return False
    if value in _INVALID_EXACT_VALUES:
        return False
    if value >= _MAX_PLAUSIBLE_PRICE:
        return False
    if value < _MIN_PLAUSIBLE_PRICE:
        return False
    return True

def is_valid_selling_price_candidate(candidate: NormalizedCandidate) -> bool:
    """
    True only if this candidate is numerically plausible AND not something
    we've identified as a non-selling-price role (shipping/EMI/discount/coupon).
    List price (MRP) is numerically valid but deprioritized, not rejected,
    at this stage - Tier 6 handles preferring selling price over MRP when
    both are present; if MRP is literally the only thing found, better to
    surface it than nothing.
    """
    if not is_plausible_amount(candidate.value):
        return False
    if candidate.role in (PriceRole.SHIPPING, PriceRole.EMI_INSTALLMENT, PriceRole.DISCOUNT_PERCENT, PriceRole.COUPON):
        return False
    return True

def filter_valid_candidates(candidates: list[NormalizedCandidate]) -> list[NormalizedCandidate]:
    return [c for c in candidates if is_valid_selling_price_candidate(c)]
