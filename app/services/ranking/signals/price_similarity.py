"""
Price similarity signal: rewards candidates priced close to a reference
price. The reference is the query product's own price when one is known
(product-to-product ranking - see rank_similar()); otherwise it falls back
to the midpoint of the user's stated budget range, if they've set one (see
UserPreferenceSnapshot). If neither exists, this signal has nothing to
compare against and sits out.

Uses a smooth exponential decay on the *relative* price difference rather
than a hard cutoff, so a candidate 10% above the reference loses only a
little ground instead of being cliffed to zero the way a fixed-band filter
would.
"""

import math

from app.services.ranking.base import RankingSignal
from app.services.ranking.types import RankingContext, SignalOutcome

# Controls how fast the score decays with relative price difference:
# ~0.90 at 5% off, ~0.67 at 20% off, ~0.14 at 100% off.
_DECAY_RATE = 2.0


class PriceSimilaritySignal(RankingSignal):
    name = "price_similarity"
    default_weight = 1.0

    def score(self, context: RankingContext) -> SignalOutcome:
        candidate_price = getattr(context.candidate, "price", None)
        if candidate_price is None or candidate_price < 0:
            return SignalOutcome(None, "No price available for this candidate.")

        reference = self._resolve_reference_price(context)
        if reference is None:
            return SignalOutcome(None, "No reference price (query price or budget) to compare against.")

        relative_diff = abs(candidate_price - reference) / reference
        value = math.exp(-_DECAY_RATE * relative_diff)
        return SignalOutcome(
            value,
            f"Priced {candidate_price:g} vs a reference of {reference:g} ({relative_diff:.0%} apart).",
        )

    def _resolve_reference_price(self, context: RankingContext) -> float | None:
        if context.query_price is not None and context.query_price > 0:
            return context.query_price

        prefs = context.user_preferences
        if prefs is None:
            return None
        lo, hi = prefs.budget_min, prefs.budget_max
        if lo is not None and hi is not None:
            return (lo + hi) / 2
        return hi if hi is not None else lo
