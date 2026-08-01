"""
Brand similarity signal: rewards candidates from the same brand as the
query product/pseudo-query. Deliberately simple string comparison (no
fuzzy-matching library, no brand-resolution network calls) - this is a
ranking tiebreaker, not app/services/brand_resolution's job of finding the
*official* brand site.
"""

from app.services.ranking.base import RankingSignal
from app.services.ranking.types import RankingContext, SignalOutcome


def _normalize(value: str | None) -> str | None:
    return value.strip().lower() if value and value.strip() else None


class BrandSimilaritySignal(RankingSignal):
    name = "brand_similarity"
    default_weight = 1.5

    def score(self, context: RankingContext) -> SignalOutcome:
        query_brand = _normalize(context.query_brand)
        candidate_brand = _normalize(getattr(context.candidate, "brand", None))

        if not query_brand or not candidate_brand:
            return SignalOutcome(None, "Brand unknown for the query or this candidate.")

        if query_brand == candidate_brand:
            return SignalOutcome(1.0, f"Same brand ({candidate_brand.title()}).")

        if query_brand in candidate_brand or candidate_brand in query_brand:
            return SignalOutcome(0.5, f"Related brand name ({candidate_brand.title()}).")

        return SignalOutcome(0.0, f"Different brand ({candidate_brand.title()}).")
