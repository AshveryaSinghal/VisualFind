"""
Review quality signal: a confidence-adjusted measure of "is this actually a
well-reviewed product", distinct from its two neighbors:

  * RatingSignal just normalizes the raw star average - a 5.0 from a single
    review scores exactly as high as a 5.0 from ten thousand.
  * ReviewCountSignal just measures volume - it doesn't know whether those
    reviews were positive.

Review quality combines both, using a Wilson score lower bound on the
"positive review" proportion (rating / 5, treated as a Bernoulli success
rate) at a 95% confidence level. A high rating backed by few reviews gets
pulled toward 0.5 (genuine uncertainty); the same rating backed by hundreds
of reviews stays near its raw value. This is the same statistic Reddit and
various e-commerce ranking systems use to rank-by-confidence rather than
rank-by-raw-average, and it needs no candidate-set context (no reference
pool stats) to compute - each candidate is scored independently.
"""

import math

from app.services.ranking.base import RankingSignal
from app.services.ranking.types import RankingContext, SignalOutcome

_Z_95 = 1.959963985  # z-score for a 95% confidence interval


class ReviewQualitySignal(RankingSignal):
    name = "review_quality"
    default_weight = 0.85

    def score(self, context: RankingContext) -> SignalOutcome:
        rating = getattr(context.candidate, "rating", None)
        count = getattr(context.candidate, "review_count", None)

        if rating is None or count is None or count <= 0:
            return SignalOutcome(None, "Not enough review data to assess quality.")

        p_hat = max(0.0, min(1.0, rating / 5.0))
        n = float(count)
        z = _Z_95

        denominator = 1.0 + (z * z) / n
        center = p_hat + (z * z) / (2.0 * n)
        spread = z * math.sqrt((p_hat * (1.0 - p_hat)) / n + (z * z) / (4.0 * n * n))
        lower_bound = (center - spread) / denominator

        value = max(0.0, min(1.0, lower_bound))
        return SignalOutcome(
            value,
            f"Rated {rating:g}/5 across {count} review(s) "
            f"(confidence-adjusted quality {value:.2f}).",
        )
