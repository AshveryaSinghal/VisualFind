from datetime import datetime, timezone

from app.models import PriceTrendPoint
from app.services import product_insights_service as insights

def _point(price: float, marketplace: str = "Amazon") -> PriceTrendPoint:
    return PriceTrendPoint(
        price=price, currency="INR", marketplace=marketplace, recorded_at=datetime.now(timezone.utc)
    )

def test_estimate_sentiment_none_without_rating():
    assert insights.estimate_sentiment(None, None) is None

def test_estimate_sentiment_high_rating_is_mostly_positive():
    sentiment = insights.estimate_sentiment(4.7, 500)
    assert sentiment is not None
    assert sentiment.positive_pct > sentiment.negative_pct
    assert sentiment.positive_pct + sentiment.neutral_pct + sentiment.negative_pct == 100
    assert "4.7" in sentiment.basis
    assert "500" in sentiment.basis

def test_estimate_sentiment_low_rating_is_mostly_negative():
    sentiment = insights.estimate_sentiment(2.1, 40)
    assert sentiment is not None
    assert sentiment.negative_pct > sentiment.positive_pct

def test_price_trend_requires_at_least_two_points():
    assert insights.price_trend([]) == (None, None)
    assert insights.price_trend([_point(100)]) == (None, None)

def test_price_trend_detects_falling_price():
    direction, change = insights.price_trend([_point(1000), _point(800)])
    assert direction == "down"
    assert change == -20.0

def test_price_trend_detects_rising_price():
    direction, change = insights.price_trend([_point(500), _point(600)])
    assert direction == "up"
    assert change == 20.0

def test_build_summary_no_history_says_so_honestly():
    bullets, verdict = insights.build_summary(rating=None, review_count=None, price_points=[])
    assert any("Not enough price history" in b for b in bullets)
    assert any("No rating data" in b for b in bullets)
    assert verdict

def test_build_summary_falling_price_and_good_rating_says_worth_buying():
    points = [_point(1200), _point(999)]
    bullets, verdict = insights.build_summary(rating=4.6, review_count=300, price_points=points)
    assert any("falling" in b for b in bullets)
    assert any("Excellent reviews" in b for b in bullets)
    assert verdict == "Worth buying now"

def test_build_summary_rising_price_says_better_to_wait():
    points = [_point(900), _point(1100)]
    _, verdict = insights.build_summary(rating=4.6, review_count=300, price_points=points)
    assert verdict == "Better to wait"

def test_build_summary_poor_rating_says_better_to_wait_even_if_price_falling():
    points = [_point(1200), _point(999)]
    _, verdict = insights.build_summary(rating=2.5, review_count=50, price_points=points)
    assert verdict == "Better to wait"
