"""
Tier 6 - Selection.

When a single strategy surfaces *multiple* plausible prices for the same
product (common on structured-metadata and rendered-DOM tiers, where a page
might expose MRP, selling price, and an EMI breakdown all as "price"-shaped
fields), pick the one that's actually the current selling price rather than
naively taking the first or the minimum.

Preference order:
  1. Any candidate explicitly labelled/roled as SELLING_PRICE.
  2. Any UNKNOWN-role candidate (couldn't tell either way - most structured
     data only exposes one real price field, so this is the common case).
  3. LIST_PRICE (MRP) only if nothing else survived Tier 5 validation -
     better to show a crossed-out MRP than nothing at all.

Within a tie, prefer the lowest price: a genuine selling price is never
higher than a decoy "was" price that leaked through, and this also
naturally favors the discounted price over a duplicate full price.
"""

from app.services.price_extraction.types import NormalizedCandidate, PriceRole

_PREFERENCE_RANK = {
    PriceRole.SELLING_PRICE: 0,
    PriceRole.UNKNOWN: 1,
    PriceRole.LIST_PRICE: 2,
}

def select_best_candidate(candidates: list[NormalizedCandidate]) -> NormalizedCandidate | None:
    """Returns the single best candidate, or None if the list is empty."""
    if not candidates:
        return None

    ranked = sorted(
        candidates,
        key=lambda c: (_PREFERENCE_RANK.get(c.role, 1), c.value),
    )
    return ranked[0]
