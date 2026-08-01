"""
Tests for PriceExtractionService (app/services/price_extraction/service.py) --
the orchestrator that walks the tier list in order and stops at the first
one that yields a valid, plausible price.

Real strategies (GoogleShoppingStrategy, HeadlessBrowserStrategy, ...) make
network calls / require API keys, so these tests use small fake strategies
that implement the same ExtractionStrategy interface. This tests the
orchestration logic itself -- ordering, fallthrough, and the never-raises
guarantee -- independent of any real data source.
"""

from app.services.price_extraction.service import PriceExtractionService
from app.services.price_extraction.strategies.base import ExtractionStrategy
from app.services.price_extraction.types import PriceCandidate, PriceRole, StrategyOutcome

class _FakeStrategy(ExtractionStrategy):
    """A controllable fake tier: returns a fixed outcome and records whether it ran."""

    def __init__(self, name: str, outcome: StrategyOutcome):
        self.name = name
        self._outcome = outcome
        self.called = False

    def _run(self, **_context) -> StrategyOutcome:
        self.called = True
        return self._outcome

class _RaisingStrategy(ExtractionStrategy):
    """A tier that blows up -- verifies the base class's exception safety."""

    name = "raising"

    def _run(self, **_context) -> StrategyOutcome:
        raise RuntimeError("simulated network failure")

def _valid_outcome(strategy_name: str, value: float = 1299.0) -> StrategyOutcome:
    return StrategyOutcome(
        strategy_name=strategy_name,
        extraction_method="fake_method",
        success=True,
        candidates=[
            PriceCandidate(
                raw_price=value,
                raw_currency="INR",
                role=PriceRole.SELLING_PRICE,
                label="fake.price",
            )
        ],
    )

def _no_valid_price_outcome(strategy_name: str) -> StrategyOutcome:
    """Succeeds at extraction, but the only price found is a shipping fee --
    Tier 5 validation should reject it, so the pipeline must move on."""
    return StrategyOutcome(
        strategy_name=strategy_name,
        extraction_method="fake_method",
        success=True,
        candidates=[
            PriceCandidate(raw_price=99, raw_currency="INR", role=PriceRole.SHIPPING, label="fake.shipping")
        ],
    )

def _outcome_with_reviews_but_no_price(strategy_name: str, rating: float, review_count: int) -> StrategyOutcome:
    """A tier that found review data on the page but no price signal at all --
    e.g. structured metadata finding aggregateRating with no parseable offer."""
    return StrategyOutcome(
        strategy_name=strategy_name,
        extraction_method="fake_method",
        success=False,
        candidates=[],
        error="no price signals found",
        rating=rating,
        review_count=review_count,
    )

def _failed_outcome(strategy_name: str) -> StrategyOutcome:
    return StrategyOutcome(
        strategy_name=strategy_name,
        extraction_method="none",
        success=False,
        candidates=[],
        error="simulated failure",
    )

class TestStopsAtFirstValidTier:
    def test_does_not_call_later_tiers_once_an_earlier_one_succeeds(self):
        tier1 = _FakeStrategy("tier1", _valid_outcome("tier1", value=999.0))
        tier2 = _FakeStrategy("tier2", _valid_outcome("tier2", value=1299.0))

        service = PriceExtractionService(strategies=[tier1, tier2])
        result = service.extract(candidate={"link": "https://amazon.in/x", "platform": "Amazon"})

        assert result.price == 999.0
        assert result.price_source == "tier1"
        assert tier1.called is True
        assert tier2.called is False

    def test_falls_through_when_the_only_candidate_fails_validation(self):

        tier1 = _FakeStrategy("tier1", _no_valid_price_outcome("tier1"))
        tier2 = _FakeStrategy("tier2", _valid_outcome("tier2", value=1299.0))

        service = PriceExtractionService(strategies=[tier1, tier2])
        result = service.extract(candidate={"link": "https://amazon.in/x", "platform": "Amazon"})

        assert result.price == 1299.0
        assert result.price_source == "tier2"
        assert tier1.called is True
        assert tier2.called is True

    def test_falls_through_a_strategy_that_reports_failure(self):
        tier1 = _FakeStrategy("tier1", _failed_outcome("tier1"))
        tier2 = _FakeStrategy("tier2", _valid_outcome("tier2"))

        service = PriceExtractionService(strategies=[tier1, tier2])
        result = service.extract(candidate={"link": "https://flipkart.com/x", "platform": "Flipkart"})

        assert result.price_source == "tier2"

class TestNeverRaises:
    def test_a_raising_strategy_is_swallowed_and_pipeline_continues(self):
        raising = _RaisingStrategy()
        tier2 = _FakeStrategy("tier2", _valid_outcome("tier2"))

        service = PriceExtractionService(strategies=[raising, tier2])

        result = service.extract(candidate={"link": "https://amazon.in/x", "platform": "Amazon"})

        assert result.price_source == "tier2"

    def test_all_tiers_failing_returns_null_result_not_an_exception(self):
        tier1 = _FakeStrategy("tier1", _failed_outcome("tier1"))
        tier2 = _RaisingStrategy()

        service = PriceExtractionService(strategies=[tier1, tier2])
        result = service.extract(candidate={"link": "https://amazon.in/x", "platform": "Amazon"})

        assert result.price is None
        assert result.currency is None
        assert result.price_source == "unavailable"
        assert result.extraction_method == "none"
        assert result.confidence_score == 0.0

class TestConfidenceOrdering:
    def test_earlier_tier_yields_higher_or_equal_confidence_than_a_later_one(self):

        tier1 = _FakeStrategy("google_shopping", _valid_outcome("google_shopping"))
        service = PriceExtractionService(strategies=[tier1])
        result = service.extract(candidate={"link": "https://amazon.in/x", "platform": "Amazon"})
        assert result.confidence_score >= 0.9

class TestReviewDataSurvivesAcrossTiers:
    def test_review_data_from_an_earlier_tier_is_kept_even_when_a_later_tier_wins_on_price(self):
        """Tier 1 (e.g. structured metadata) found rating/reviews but no
        usable price; Tier 2 wins on price. The final result must still
        carry the review data Tier 1 found - it must not be thrown away
        just because a different tier ended up supplying the price."""
        tier1 = _FakeStrategy("structured_metadata", _outcome_with_reviews_but_no_price(
            "structured_metadata", rating=4.4, review_count=210
        ))
        tier2 = _FakeStrategy("headless_browser", _valid_outcome("headless_browser", value=1499.0))

        service = PriceExtractionService(strategies=[tier1, tier2])
        result = service.extract(candidate={"link": "https://amazon.in/x", "platform": "Amazon"})

        assert result.price == 1499.0
        assert result.price_source == "headless_browser"
        assert result.rating == 4.4
        assert result.review_count == 210

    def test_review_data_is_kept_even_when_every_tier_fails_on_price(self):
        tier1 = _FakeStrategy("structured_metadata", _outcome_with_reviews_but_no_price(
            "structured_metadata", rating=3.8, review_count=64
        ))

        service = PriceExtractionService(strategies=[tier1])
        result = service.extract(candidate={"link": "https://amazon.in/x", "platform": "Amazon"})

        assert result.price is None
        assert result.price_source == "unavailable"
        assert result.rating == 3.8
        assert result.review_count == 64

    def test_an_earlier_tier_that_already_found_reviews_is_not_overwritten_by_a_later_one(self):
        tier1 = _FakeStrategy("structured_metadata", _outcome_with_reviews_but_no_price(
            "structured_metadata", rating=4.9, review_count=5
        ))
        tier2_outcome = _valid_outcome("google_shopping", value=999.0)
        tier2_outcome.rating = 2.0
        tier2_outcome.review_count = 1
        tier2 = _FakeStrategy("google_shopping", tier2_outcome)

        service = PriceExtractionService(strategies=[tier1, tier2])
        result = service.extract(candidate={"link": "https://amazon.in/x", "platform": "Amazon"})

        assert result.rating == 4.9
        assert result.review_count == 5
