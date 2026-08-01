"""Rating signal: a plain 0-5 star rating normalized to 0..1."""

from app.services.ranking.base import RankingSignal
from app.services.ranking.types import RankingContext, SignalOutcome


class RatingSignal(RankingSignal):
    name = "rating"
    default_weight = 1.0

    def score(self, context: RankingContext) -> SignalOutcome:
        rating = getattr(context.candidate, "rating", None)
        if rating is None:
            return SignalOutcome(None, "No rating available for this candidate.")

        value = max(0.0, min(1.0, rating / 5.0))
        return SignalOutcome(value, f"Rated {rating:g}/5.")
