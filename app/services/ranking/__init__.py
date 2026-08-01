"""
The Ranking Engine.

Instead of ordering search results by image similarity alone, this package
blends multiple independent signals into one explainable score per
product:

  visual_similarity, text_relevance, brand_similarity, category_similarity,
  price_similarity, rating, review_count, review_quality, user_preference,
  search_history, popularity, freshness

See:
  * base.py            - the RankingSignal interface every signal implements
  * signals/            - the twelve built-in signals, one per file
  * registry.py         - where signals are registered/looked up by name
  * engine.py           - RankingEngine, which weighs + explains + sorts
  * types.py            - the plain-dataclass context/result types
  * context_builders.py - the one place that turns DB state (user
                           preferences, search history) into those types

Callers outside this package (see app/services/product_index/service.py)
should go through `build_engine()` below rather than instantiating
RankingEngine directly, so weight overrides configured in
`settings.ranking_weights_json` are always picked up.
"""

from app.config import settings

from .base import RankingSignal
from .engine import RankingEngine
from .registry import available_signals, get_signal, register_signal
from .types import (
    RankedProduct,
    RankedScore,
    RankingContext,
    SearchHistorySnapshot,
    SignalContribution,
    SignalOutcome,
    UserPreferenceSnapshot,
)


def build_engine(signal_names: list[str] | None = None) -> RankingEngine:
    """The engine the rest of the app should use. Resolves
    `settings.ranking_weight_overrides` fresh on every call - same
    "never cache a config snapshot" convention as
    embedding_backends.get_backend() - so a weight tweak in `.env` takes
    effect on the next request, not the next restart."""
    return RankingEngine(weights=settings.ranking_weight_overrides, signal_names=signal_names)


__all__ = [
    "RankingSignal",
    "RankingEngine",
    "available_signals",
    "get_signal",
    "register_signal",
    "build_engine",
    "RankedProduct",
    "RankedScore",
    "RankingContext",
    "SearchHistorySnapshot",
    "SignalContribution",
    "SignalOutcome",
    "UserPreferenceSnapshot",
]
