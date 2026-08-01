"""
The swap/extension point for ranking signals.

`RankingEngine` (see engine.py) never computes a signal's math itself - it
only ever calls `.score(context)` on whatever `RankingSignal`s are
registered (see registry.py). To add a brand-new ranking signal, write one
class implementing this interface, add it to registry.py's `_REGISTRY` (or
call `register_signal(...)` at runtime), and optionally give it a default
weight in app/config.py's `ranking_weights_json`. No other file needs to
change - not this one, not engine.py, not the callers in
product_index/service.py.
"""

from abc import ABC, abstractmethod

from app.services.ranking.types import RankingContext, SignalOutcome


class RankingSignal(ABC):
    """One ranking signal.

    `name` must be a short, stable identifier (e.g. "visual_similarity",
    "brand_similarity") - it's how weight overrides
    (`settings.ranking_weight_overrides`) and explanations refer to this
    signal, and how the registry is keyed.

    `default_weight` is used whenever no override is configured for this
    signal's name. Signals are free to weigh more or less than 1.0 by
    default (e.g. visual similarity dominates by default; freshness is a
    light tiebreaker) - that's a starting point, not a hard-coded ranking;
    every weight is overridable without touching this class.
    """

    name: str
    default_weight: float = 1.0

    @abstractmethod
    def score(self, context: RankingContext) -> SignalOutcome:
        """Returns a 0..1 relevance score for `context.candidate`, plus a
        short human-readable explanation of *why*. Return
        `SignalOutcome(None, "...")` - never raise, never guess - when this
        signal genuinely has no data to compare (e.g. no rating on either
        side); the engine treats a None value as "this signal sits out for
        this candidate" and renormalizes the remaining weights rather than
        scoring it as zero (which would unfairly penalize candidates
        missing a field that has nothing to do with their actual
        relevance).
        """
        raise NotImplementedError
