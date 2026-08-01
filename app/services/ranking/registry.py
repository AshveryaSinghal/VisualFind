"""
Registry of available ranking signals, keyed by `RankingSignal.name` - the
same "swap/extend via registration, not via editing the engine" convention
used for embedding backends (see
app/services/product_index/embedding_backends/__init__.py).

Adding a new ranking signal to production is meant to be exactly this:
implement a `RankingSignal` (see base.py and signals/ for examples),
`register_signal(...)` it - or add it to `_REGISTRY` below - and give it a
weight (its own `default_weight`, or an override in
`settings.ranking_weights_json`). No other file - not engine.py, not
product_index/service.py, not search_service.py - needs to change.
"""

from .base import RankingSignal
from .signals import (
    BrandSimilaritySignal,
    CategorySimilaritySignal,
    FreshnessSignal,
    PopularitySignal,
    PriceSimilaritySignal,
    RatingSignal,
    ReviewCountSignal,
    ReviewQualitySignal,
    SearchHistorySignal,
    TextRelevanceSignal,
    UserPreferenceSignal,
    VisualSimilaritySignal,
)

_REGISTRY: dict[str, type[RankingSignal]] = {
    VisualSimilaritySignal.name: VisualSimilaritySignal,
    TextRelevanceSignal.name: TextRelevanceSignal,
    BrandSimilaritySignal.name: BrandSimilaritySignal,
    CategorySimilaritySignal.name: CategorySimilaritySignal,
    PriceSimilaritySignal.name: PriceSimilaritySignal,
    RatingSignal.name: RatingSignal,
    ReviewCountSignal.name: ReviewCountSignal,
    ReviewQualitySignal.name: ReviewQualitySignal,
    UserPreferenceSignal.name: UserPreferenceSignal,
    SearchHistorySignal.name: SearchHistorySignal,
    PopularitySignal.name: PopularitySignal,
    FreshnessSignal.name: FreshnessSignal,
}


def register_signal(signal_cls: type[RankingSignal]) -> None:
    """Adds (or replaces) an entry in the signal registry. Call this once
    - e.g. at app startup, or from a test - to make a new/custom signal
    available to `RankingEngine`."""
    _REGISTRY[signal_cls.name] = signal_cls


def available_signals() -> list[str]:
    return sorted(_REGISTRY.keys())


def get_signal(name: str) -> RankingSignal:
    """Resolves and instantiates one signal by name. Raises ValueError for
    an unregistered name rather than silently skipping it, since that
    almost always means a typo'd config value or signal_names list."""
    try:
        signal_cls = _REGISTRY[name]
    except KeyError:
        raise ValueError(f"Unknown ranking signal '{name}'. Registered signals: {available_signals()}")
    return signal_cls()


def default_weights() -> dict[str, float]:
    """Every registered signal's out-of-the-box weight, before any
    `settings.ranking_weight_overrides` are applied."""
    return {name: signal_cls().default_weight for name, signal_cls in _REGISTRY.items()}
