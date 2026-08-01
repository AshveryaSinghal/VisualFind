"""
Tests for the Ranking Engine itself (app/services/ranking/engine.py,
base.py, registry.py) - pure, DB-free, no fixtures beyond plain dataclasses
and stub signals. See test_ranking_signals.py for the individual built-in
signals, and test_product_index_ranking.py for how the engine gets wired
into product_index_service.rank_matches()/rank_similar().
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.services.ranking.base import RankingSignal
from app.services.ranking.engine import RankingEngine
from app.services.ranking.registry import (
    available_signals,
    default_weights,
    get_signal,
    register_signal,
)
from app.services.ranking.types import RankingContext, SignalOutcome


def _candidate(**overrides):
    base = dict(
        title="Product",
        brand="Sony",
        category="electronics",
        price=1000.0,
        rating=4.5,
        review_count=100,
        source="Amazon",
        times_seen=5,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    base.update(overrides)
    return SimpleNamespace(**base)


# --- registry ---

def test_available_signals_includes_all_twelve_built_ins():
    names = available_signals()
    assert names == sorted(
        [
            "visual_similarity",
            "text_relevance",
            "brand_similarity",
            "category_similarity",
            "price_similarity",
            "rating",
            "review_count",
            "review_quality",
            "user_preference",
            "search_history",
            "popularity",
            "freshness",
        ]
    )


def test_get_signal_raises_for_unknown_name():
    with pytest.raises(ValueError, match="Unknown ranking signal"):
        get_signal("does_not_exist")


def test_default_weights_matches_each_signals_default_weight():
    weights = default_weights()
    assert weights["visual_similarity"] == get_signal("visual_similarity").default_weight
    assert weights["freshness"] == get_signal("freshness").default_weight


def test_registering_a_brand_new_signal_requires_no_engine_changes():
    """The whole point of the registry: a new signal is one class plus one
    register_signal() call - RankingEngine picks it up with zero other
    changes."""

    class AlwaysHalfSignal(RankingSignal):
        name = "always_half_test_signal"
        default_weight = 1.0

        def score(self, context):
            return SignalOutcome(0.5, "always half")

    register_signal(AlwaysHalfSignal)
    try:
        engine = RankingEngine(signal_names=["always_half_test_signal"])
        result = engine.score(RankingContext(candidate=_candidate()))
        assert result.total_score == 0.5
        assert result.contributions[0].name == "always_half_test_signal"
    finally:
        # Don't leak this test signal into other tests' registry state.
        from app.services.ranking import registry as _registry

        del _registry._REGISTRY["always_half_test_signal"]


# --- engine scoring mechanics ---

def test_engine_blends_multiple_applicable_signals_by_weight():
    class FixedSignal(RankingSignal):
        def __init__(self, name, value, weight):
            self.name = name
            self.default_weight = weight
            self._value = value

        def score(self, context):
            return SignalOutcome(self._value, f"{self.name}={self._value}")

    engine = RankingEngine(signal_names=[])
    engine._signals = [FixedSignal("a", 1.0, 1.0), FixedSignal("b", 0.0, 1.0)]
    engine._weights = {"a": 1.0, "b": 1.0}

    result = engine.score(RankingContext(candidate=_candidate()))
    assert result.total_score == 0.5  # (1.0*1 + 0.0*1) / (1+1)


def test_engine_renormalizes_when_a_signal_has_no_data():
    """A signal returning None (no data) must not drag the score toward
    zero - its weight is excluded from the denominator entirely."""

    class FixedSignal(RankingSignal):
        def __init__(self, name, value, weight):
            self.name = name
            self.default_weight = weight
            self._value = value

        def score(self, context):
            if self._value is None:
                return SignalOutcome(None, "no data")
            return SignalOutcome(self._value, "ok")

    engine = RankingEngine(signal_names=[])
    engine._signals = [FixedSignal("a", 1.0, 1.0), FixedSignal("b", None, 5.0)]
    engine._weights = {"a": 1.0, "b": 5.0}

    result = engine.score(RankingContext(candidate=_candidate()))
    # If "b" (weight 5) had been scored as 0 instead of excluded, this would
    # be 1/6 ~= 0.1667. Renormalized (b excluded entirely), it's 1.0.
    assert result.total_score == 1.0
    applied = [c for c in result.contributions if c.applied]
    assert len(applied) == 1
    assert applied[0].name == "a"


def test_engine_treats_a_raising_signal_as_not_applicable_rather_than_crashing():
    class ExplodingSignal(RankingSignal):
        name = "exploding_test_signal"
        default_weight = 1.0

        def score(self, context):
            raise RuntimeError("boom")

    engine = RankingEngine(signal_names=[])
    engine._signals = [ExplodingSignal()]
    engine._weights = {"exploding_test_signal": 1.0}

    result = engine.score(RankingContext(candidate=_candidate()))
    assert result.total_score == 0.0
    assert result.contributions[0].applied is False


def test_zero_or_negative_weight_excludes_a_signal_entirely():
    class FixedSignal(RankingSignal):
        name = "zero_weight_test_signal"
        default_weight = 1.0

        def score(self, context):
            return SignalOutcome(0.9, "shouldn't matter")

    engine = RankingEngine(signal_names=[], weights={})
    engine._signals = [FixedSignal()]
    engine._weights = {"zero_weight_test_signal": 0.0}

    result = engine.score(RankingContext(candidate=_candidate()))
    assert result.total_score == 0.0
    assert result.contributions == []


def test_weight_overrides_only_apply_to_known_signal_names():
    engine = RankingEngine(weights={"visual_similarity": 9.0, "not_a_real_signal": 5.0})
    assert engine._weights["visual_similarity"] == 9.0
    assert "not_a_real_signal" not in engine._weights


def test_engine_rank_sorts_candidates_by_total_score_descending():
    class ByCandidatePriceSignal(RankingSignal):
        name = "by_price_test_signal"
        default_weight = 1.0

        def score(self, context):
            # Lower price -> higher score, purely so we can assert ordering.
            return SignalOutcome(1.0 / context.candidate.price, "ok")

    register_signal(ByCandidatePriceSignal)
    try:
        engine = RankingEngine(signal_names=["by_price_test_signal"])
        cheap = _candidate(price=1.0)
        mid = _candidate(price=2.0)
        pricey = _candidate(price=10.0)

        contexts = [
            (cheap, RankingContext(candidate=cheap)),
            (pricey, RankingContext(candidate=pricey)),
            (mid, RankingContext(candidate=mid)),
        ]
        ranked = engine.rank(contexts)
        assert [r.candidate for r in ranked] == [cheap, mid, pricey]
        assert ranked[0].score.total_score > ranked[1].score.total_score > ranked[2].score.total_score
    finally:
        from app.services.ranking import registry as _registry

        del _registry._REGISTRY["by_price_test_signal"]


def test_summary_prefers_the_highest_weighted_contributors():
    class FixedSignal(RankingSignal):
        def __init__(self, name, value, weight):
            self.name = name
            self.default_weight = weight
            self._value = value

        def score(self, context):
            return SignalOutcome(self._value, f"reason-{self.name}")

    engine = RankingEngine(signal_names=[])
    engine._signals = [
        FixedSignal("big", 1.0, 10.0),
        FixedSignal("small", 1.0, 0.1),
    ]
    engine._weights = {"big": 10.0, "small": 0.1}

    result = engine.score(RankingContext(candidate=_candidate()))
    assert "reason-big" in result.summary


def test_no_applicable_signals_yields_zero_score_and_explanatory_summary():
    class NoDataSignal(RankingSignal):
        name = "no_data_test_signal"
        default_weight = 1.0

        def score(self, context):
            return SignalOutcome(None, "nothing to compare")

    engine = RankingEngine(signal_names=[])
    engine._signals = [NoDataSignal()]
    engine._weights = {"no_data_test_signal": 1.0}

    result = engine.score(RankingContext(candidate=_candidate()))
    assert result.total_score == 0.0
    assert "No ranking signals" in result.summary
