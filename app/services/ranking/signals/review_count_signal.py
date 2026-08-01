"""
Review count signal: more reviews means more confidence in a product's
rating, but with strongly diminishing returns - 1,000 reviews shouldn't
dominate 100 the way a raw linear count would. Log-scaled against the
highest review count seen anywhere in the current candidate set
(`RankingContext.reference_max_review_count`, computed once per ranking
call - see product_index/service.py), so the signal is always relative to
"how popular is this search's results, right now" rather than some
hardcoded ceiling that would need retuning as the catalog grows.
"""

import math

from app.services.ranking.base import RankingSignal
from app.services.ranking.types import RankingContext, SignalOutcome


class ReviewCountSignal(RankingSignal):
    name = "review_count"
    default_weight = 0.75

    def score(self, context: RankingContext) -> SignalOutcome:
        count = getattr(context.candidate, "review_count", None)
        if count is None or count < 0:
            return SignalOutcome(None, "No review count available for this candidate.")

        ceiling = max(context.reference_max_review_count, count, 1)
        value = math.log1p(count) / math.log1p(ceiling)
        return SignalOutcome(value, f"{count} review(s).")
