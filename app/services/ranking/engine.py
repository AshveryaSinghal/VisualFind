"""
The Ranking Engine: blends every configured RankingSignal (see registry.py
and signals/) into one explainable score per candidate.

Design goals, and how each is met:

  * "Adding a new signal later requires minimal code changes" - a new
    signal is one new file under signals/ implementing RankingSignal, plus
    one line in registry.py's _REGISTRY (or a runtime register_signal()
    call). This file never changes.
  * "Each signal should have configurable weights" - every signal carries
    its own `default_weight`, overridable per-signal via
    `settings.ranking_weights_json` (see app/config.py), with no code
    change required to retune them.
  * "Return an explainable score for every product" - RankedScore carries
    every signal's raw score, weight, weighted contribution, and a
    plain-language explanation, plus a short human-readable summary of the
    top contributors.
  * "Modular and testable" - RankingEngine takes plain RankingContext
    objects in and RankedProduct objects out; it never touches a database,
    HTTP request, or settings object itself (that wiring lives in
    product_index/service.py), so it can be exercised directly in unit
    tests with hand-built contexts and no fixtures.

A signal that raises, or that returns SignalOutcome(None, ...) because it
has nothing to say about a given candidate (e.g. no rating on either
side), is excluded from that candidate's score entirely - its weight is
left out of the denominator too, so missing data never silently drags a
candidate's score toward zero the way scoring it as 0.0 would.
"""

import logging

from app.services.ranking import registry
from app.services.ranking.types import RankedProduct, RankedScore, RankingContext, SignalContribution

logger = logging.getLogger(__name__)

_SUMMARY_TOP_N = 3


class RankingEngine:
    """Construct directly with explicit `weights`/`signal_names` for tests
    or a one-off custom pipeline. In app code, prefer
    `app.services.ranking.build_engine()` instead of instantiating this
    yourself - it resolves `settings.ranking_weight_overrides` fresh on
    every call, the same "always reflect current config, no cached
    instance to go stale" convention as
    embedding_backends.get_backend()."""

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        signal_names: list[str] | None = None,
    ):
        names = signal_names if signal_names is not None else registry.available_signals()
        self._signals = [registry.get_signal(name) for name in names]
        self._weights = {signal.name: signal.default_weight for signal in self._signals}
        if weights:
            self._weights.update({name: value for name, value in weights.items() if name in self._weights})

    @property
    def signal_names(self) -> list[str]:
        return [signal.name for signal in self._signals]

    def score(self, context: RankingContext) -> RankedScore:
        """Scores a single candidate (already wrapped in a RankingContext)
        against every configured signal, weight-averaging whichever
        signals actually had something to say."""
        contributions: list[SignalContribution] = []
        weighted_sum = 0.0
        weight_total = 0.0

        for signal in self._signals:
            weight = self._weights.get(signal.name, signal.default_weight)
            if weight <= 0:
                continue

            try:
                outcome = signal.score(context)
            except Exception:
                logger.exception("Ranking signal %r raised; treating as not applicable", signal.name)
                contributions.append(
                    SignalContribution(signal.name, weight, None, 0.0, False, "Signal failed to score; skipped.")
                )
                continue

            if outcome.value is None:
                contributions.append(
                    SignalContribution(signal.name, weight, None, 0.0, False, outcome.explanation)
                )
                continue

            raw_score = max(0.0, min(1.0, outcome.value))
            weighted_score = raw_score * weight
            weighted_sum += weighted_score
            weight_total += weight
            contributions.append(
                SignalContribution(signal.name, weight, raw_score, weighted_score, True, outcome.explanation)
            )

        total_score = round(weighted_sum / weight_total, 4) if weight_total > 0 else 0.0
        return RankedScore(total_score=total_score, contributions=contributions, summary=self._summarize(contributions))

    def rank(self, candidates_with_context) -> list[RankedProduct]:
        """`candidates_with_context`: an iterable of (candidate, RankingContext)
        pairs. The engine doesn't build contexts itself - only the caller
        knows how to fetch a candidate's own metadata/user context - it
        just scores and sorts. Returns candidates sorted by total_score,
        highest first."""
        ranked = [RankedProduct(candidate, self.score(context)) for candidate, context in candidates_with_context]
        ranked.sort(key=lambda item: item.score.total_score, reverse=True)
        return ranked

    def _summarize(self, contributions: list[SignalContribution]) -> str:
        applied = [c for c in contributions if c.applied]
        if not applied:
            return "No ranking signals had enough data to score this candidate."
        top = sorted(applied, key=lambda c: c.weighted_score, reverse=True)[:_SUMMARY_TOP_N]
        return " ".join(c.explanation for c in top)
