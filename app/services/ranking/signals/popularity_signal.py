"""
Popularity signal: how many completed searches have already surfaced this
exact catalog row (`ProductIndexEntry.times_seen` - see
product_index/service.py::upsert_product). Log-scaled against the
most-seen candidate in the current set (`reference_max_times_seen`) so one
runaway-popular item doesn't flatten every other candidate's score to
near-zero.
"""

import math

from app.services.ranking.base import RankingSignal
from app.services.ranking.types import RankingContext, SignalOutcome


class PopularitySignal(RankingSignal):
    name = "popularity"
    default_weight = 0.5

    def score(self, context: RankingContext) -> SignalOutcome:
        times_seen = getattr(context.candidate, "times_seen", None)
        if not times_seen:
            return SignalOutcome(None, "No popularity data for this candidate.")

        ceiling = max(context.reference_max_times_seen, times_seen, 1)
        value = math.log1p(times_seen) / math.log1p(ceiling)
        return SignalOutcome(value, f"Seen in {times_seen} completed search(es).")
