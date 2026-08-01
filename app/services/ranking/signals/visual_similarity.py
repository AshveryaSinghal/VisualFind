"""
Visual similarity signal.

Doesn't compute anything itself - the embedding/cosine-similarity math
already lives in app/services/product_index/embedding_service.py, and
re-deriving it per-candidate here would just be redoing work the caller
already did. This signal reads the precomputed value straight off
`RankingContext.visual_similarity` and passes it through, clamped to
[0, 1].

Keeping it as a real, registered signal (rather than a special-cased "add
this in separately" constant) means it participates in the exact same
weighting/explanation/renormalization machinery as every other signal -
e.g. it can be turned down relative to brand/price for a known-noisy
embedding backend purely via a weight-config change, no engine code touched.
"""

from app.services.ranking.base import RankingSignal
from app.services.ranking.types import RankingContext, SignalOutcome


class VisualSimilaritySignal(RankingSignal):
    name = "visual_similarity"
    # Dominant by default - this is still primarily an image search engine.
    default_weight = 3.0

    def score(self, context: RankingContext) -> SignalOutcome:
        if context.visual_similarity is None:
            return SignalOutcome(None, "No image embedding similarity available for this candidate.")
        value = max(0.0, min(1.0, context.visual_similarity))
        return SignalOutcome(value, f"Visually {value:.0%} similar to the query image.")
