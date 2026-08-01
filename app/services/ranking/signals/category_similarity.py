"""
Category similarity signal: rewards candidates in the same product
category as the query (see app/services/preferences_service.categorize_text
for how a category gets assigned in the first place - callers of the
ranking engine are responsible for populating `query_category`/
`candidate.category` with that same vocabulary before scoring, so this
signal just compares two already-resolved category values).
"""

from app.services.ranking.base import RankingSignal
from app.services.ranking.types import RankingContext, SignalOutcome


class CategorySimilaritySignal(RankingSignal):
    name = "category_similarity"
    default_weight = 1.0

    def score(self, context: RankingContext) -> SignalOutcome:
        query_category = context.query_category
        candidate_category = getattr(context.candidate, "category", None)

        if not query_category or not candidate_category:
            return SignalOutcome(None, "Category unknown for the query or this candidate.")

        if query_category == candidate_category:
            return SignalOutcome(1.0, f"Same category ({candidate_category}).")

        return SignalOutcome(0.0, f"Different category ({candidate_category}).")
