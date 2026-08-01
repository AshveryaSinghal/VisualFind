"""
Freshness signal: how recently this catalog row was last refreshed
(`ProductIndexEntry.updated_at`, falling back to `created_at` for a row
that's never been re-seen). Decays smoothly with a configurable half-life
rather than a hard "new vs stale" cutoff, so a two-week-old listing still
earns partial credit instead of none.
"""

import math
from datetime import timezone

from app.services.ranking.base import RankingSignal
from app.services.ranking.types import RankingContext, SignalOutcome

_HALF_LIFE_DAYS = 30.0


class FreshnessSignal(RankingSignal):
    name = "freshness"
    default_weight = 0.5

    def score(self, context: RankingContext) -> SignalOutcome:
        candidate = context.candidate
        timestamp = getattr(candidate, "updated_at", None) or getattr(candidate, "created_at", None)
        if timestamp is None:
            return SignalOutcome(None, "No timestamp available for this candidate.")

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        age_days = max(0.0, (context.reference_now - timestamp).total_seconds() / 86400.0)
        value = math.pow(0.5, age_days / _HALF_LIFE_DAYS)
        return SignalOutcome(value, f"Last refreshed {age_days:.0f} day(s) ago.")
