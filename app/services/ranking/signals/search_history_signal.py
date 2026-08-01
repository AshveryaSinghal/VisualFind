"""
Search history relevance signal: boosts candidates whose brand or category
shows up frequently in this user's own recent searches (see
context_builders.py::load_search_history_snapshot - the only place that
reads SearchLog; this signal only ever sees the already-summarized
SearchHistorySnapshot). Purely frequency-based over the lookback window
the snapshot was built with - no separate recency decay here, since the
lookback itself already limits how far back "recent" reaches.
"""

from app.services.ranking.base import RankingSignal
from app.services.ranking.types import RankingContext, SignalOutcome

# A brand/category making up roughly a third or more of a user's recent
# searches is treated as a strong, maxed-out signal rather than needing to
# approach 100% (which would require a user to have searched for almost
# nothing else).
_SATURATION_SHARE = 1.0 / 3.0


class SearchHistorySignal(RankingSignal):
    name = "search_history"
    default_weight = 1.0

    def score(self, context: RankingContext) -> SignalOutcome:
        history = context.search_history
        if history is None or (not history.brand_counts and not history.category_counts):
            return SignalOutcome(None, "No search history available for this user.")

        brand_share = history.brand_share(getattr(context.candidate, "brand", None))
        category_share = history.category_share(getattr(context.candidate, "category", None))
        shares = [s for s in (brand_share, category_share) if s is not None]

        if not shares:
            return SignalOutcome(0.0, "Doesn't match this user's recent search brands/categories.")

        value = min(1.0, max(shares) / _SATURATION_SHARE)
        return SignalOutcome(value, "Matches a brand/category from this user's recent searches.")
