from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.services import review_sentiment_service as svc


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _offer(**overrides) -> dict:
    base = {
        "title": "Wireless Headphones",
        "link": "https://www.amazon.com/dp/B000TEST",
        "price": 1999,
        "currency": "INR",
        "rating": 4.5,
        "reviews": 100,
        "thumbnail": None,
        "source": "Amazon.in",
        "page_token": "tok-abc",
    }
    base.update(overrides)
    return base


def _review(text: str, title: str | None = None, rating: float = 5) -> dict:
    return {"title": title, "text": text, "rating": rating, "date": "1 month ago", "source": "Amazon"}


class TestSelectPageToken:
    def test_prefers_exact_link_match(self):
        offers = [
            _offer(link="https://www.amazon.com/dp/OTHER", page_token="wrong-token"),
            _offer(link="https://www.amazon.com/dp/RIGHT", page_token="right-token"),
        ]
        token = svc._select_page_token(offers, platform=None, link="https://www.amazon.com/dp/RIGHT")
        assert token == "right-token"

    def test_falls_back_to_first_offer_with_a_token(self):
        offers = [_offer(page_token=None), _offer(page_token="only-token")]
        token = svc._select_page_token(offers, platform=None, link=None)
        assert token == "only-token"

    def test_returns_none_when_no_offer_has_a_token(self):
        offers = [_offer(page_token=None)]
        assert svc._select_page_token(offers, platform=None, link=None) is None


class TestScoreReview:
    def test_positive_text_scores_positive(self):
        assert svc._score_review(_review("Absolutely love this, best purchase ever!")) == "positive"

    def test_negative_text_scores_negative(self):
        assert svc._score_review(_review("Terrible quality, broke after one day, awful.")) == "negative"

    def test_neutral_text_scores_neutral(self):
        assert svc._score_review(_review("It is a pair of headphones. Arrived on Tuesday.")) == "neutral"


class TestBuildRealSentiment:
    def test_percentages_sum_to_100_and_reflect_mix(self):
        reviews = [
            _review("Amazing sound quality, I love it!"),
            _review("Great value, highly recommend."),
            _review("Broke within a week, terrible experience."),
            _review("It's fine, does the job."),
        ]
        sentiment = svc._build_real_sentiment(reviews)

        assert sentiment.is_estimate is False
        assert sentiment.review_count_analyzed == 4
        assert sentiment.positive_pct + sentiment.neutral_pct + sentiment.negative_pct == 100
        assert sentiment.positive_pct > sentiment.negative_pct
        assert "4 actual reviews" in sentiment.basis
        assert sentiment.sample_positive is not None
        assert sentiment.sample_negative is not None


class TestGetSentiment:
    def test_uses_real_reviews_when_enough_are_found(self):
        db = _session()
        offers = [_offer()]
        reviews = [
            _review("Fantastic! Love it, works perfectly."),
            _review("Really great product, very happy."),
            _review("Terrible, stopped working after two days."),
        ]
        with patch("app.services.review_sentiment_service.settings") as mock_settings, patch(
            "app.services.review_sentiment_service.fetch_offers_for_query", return_value=offers
        ), patch.object(svc, "_fetch_reviews", return_value=reviews):
            mock_settings.enable_real_review_sentiment = True
            mock_settings.review_sentiment_min_reviews = 3
            mock_settings.review_sentiment_max_reviews = 25

            sentiment = svc.get_sentiment(
                db, title="Wireless Headphones", platform=None, link=None, rating=4.5, review_count=100
            )

        assert sentiment is not None
        assert sentiment.is_estimate is False
        assert sentiment.review_count_analyzed == 3

    def test_falls_back_to_estimate_when_too_few_real_reviews(self):
        db = _session()
        offers = [_offer()]
        reviews = [_review("Great!")]  # below min_reviews
        with patch("app.services.review_sentiment_service.settings") as mock_settings, patch(
            "app.services.review_sentiment_service.fetch_offers_for_query", return_value=offers
        ), patch.object(svc, "_fetch_reviews", return_value=reviews):
            mock_settings.enable_real_review_sentiment = True
            mock_settings.review_sentiment_min_reviews = 3
            mock_settings.review_sentiment_max_reviews = 25

            sentiment = svc.get_sentiment(
                db, title="Wireless Headphones", platform=None, link=None, rating=4.5, review_count=100
            )

        assert sentiment is not None
        assert sentiment.is_estimate is True

    def test_falls_back_to_estimate_when_no_page_token_found(self):
        db = _session()
        with patch("app.services.review_sentiment_service.settings") as mock_settings, patch(
            "app.services.review_sentiment_service.fetch_offers_for_query", return_value=[]
        ):
            mock_settings.enable_real_review_sentiment = True

            sentiment = svc.get_sentiment(
                db, title="Wireless Headphones", platform=None, link=None, rating=4.5, review_count=100
            )

        assert sentiment is not None
        assert sentiment.is_estimate is True

    def test_disabled_setting_skips_real_lookup_entirely(self):
        db = _session()
        with patch("app.services.review_sentiment_service.settings") as mock_settings, patch(
            "app.services.review_sentiment_service.fetch_offers_for_query"
        ) as mock_fetch:
            mock_settings.enable_real_review_sentiment = False

            sentiment = svc.get_sentiment(
                db, title="Wireless Headphones", platform=None, link=None, rating=4.5, review_count=100
            )

        mock_fetch.assert_not_called()
        assert sentiment is not None
        assert sentiment.is_estimate is True

    def test_returns_none_when_no_rating_and_no_real_reviews(self):
        db = _session()
        with patch("app.services.review_sentiment_service.settings") as mock_settings, patch(
            "app.services.review_sentiment_service.fetch_offers_for_query", return_value=[]
        ):
            mock_settings.enable_real_review_sentiment = True

            sentiment = svc.get_sentiment(
                db, title="Wireless Headphones", platform=None, link=None, rating=None, review_count=None
            )

        assert sentiment is None
