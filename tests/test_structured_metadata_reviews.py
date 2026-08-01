"""
Tests for the rating/review-count extraction added to
StructuredMetadataStrategy (app/services/price_extraction/strategies/structured_metadata.py).

Network access is mocked via a fake `requests.get` response so these run
offline/deterministically, same approach the rest of the extraction-tier
tests use (no real HTTP calls in this suite).
"""

from unittest.mock import patch

from app.services.price_extraction.strategies.structured_metadata import StructuredMetadataStrategy


class _FakeResponse:
    def __init__(self, text: str, status_code: int = 200):
        self.text = text
        self.status_code = status_code


def _run_strategy(html: str):
    strategy = StructuredMetadataStrategy()
    with patch("app.services.price_extraction.strategies.structured_metadata.requests.get") as mock_get, \
         patch("app.config.settings.enable_page_metadata_fallback", True), \
         patch("app.config.settings.page_metadata_fetch_timeout_seconds", 5):
        mock_get.return_value = _FakeResponse(html)
        return strategy.run(url="https://example.com/product/1", platform="Amazon")


class TestJsonLdAggregateRating:
    def test_extracts_rating_and_review_count_from_aggregate_rating(self):
        html = """
        <html><head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org/",
          "@type": "Product",
          "name": "Wireless Headphones",
          "offers": {"@type": "Offer", "price": "1999", "priceCurrency": "INR"},
          "aggregateRating": {
            "@type": "AggregateRating",
            "ratingValue": "4.6",
            "reviewCount": "1284"
          }
        }
        </script>
        </head><body></body></html>
        """
        outcome = _run_strategy(html)

        assert outcome.success is True
        assert outcome.rating == 4.6
        assert outcome.review_count == 1284

    def test_falls_back_to_rating_count_when_review_count_is_absent(self):
        html = """
        <script type="application/ld+json">
        {
          "@type": "Product",
          "offers": {"price": "499"},
          "aggregateRating": {"ratingValue": 4.1, "ratingCount": 322}
        }
        </script>
        """
        outcome = _run_strategy(html)

        assert outcome.rating == 4.1
        assert outcome.review_count == 322

    def test_handles_graph_wrapped_json_ld(self):
        html = """
        <script type="application/ld+json">
        {
          "@graph": [
            {"@type": "WebPage", "name": "Some page"},
            {
              "@type": "Product",
              "offers": {"price": "799"},
              "aggregateRating": {"ratingValue": "3.9", "reviewCount": "50"}
            }
          ]
        }
        </script>
        """
        outcome = _run_strategy(html)

        assert outcome.rating == 3.9
        assert outcome.review_count == 50

    def test_review_data_is_still_returned_when_no_usable_price_is_found(self):
        """A page with review data but nothing this tier recognizes as a price
        must still surface the review data - later tiers finding the price
        shouldn't cause it to be discarded."""
        html = """
        <script type="application/ld+json">
        {"@type": "Product", "aggregateRating": {"ratingValue": "4.0", "reviewCount": "12"}}
        </script>
        """
        outcome = _run_strategy(html)

        assert outcome.success is False
        assert outcome.rating == 4.0
        assert outcome.review_count == 12


class TestMicrodataFallback:
    def test_extracts_rating_from_itemprop_when_no_json_ld_present(self):
        html = """
        <div itemscope itemtype="https://schema.org/Product">
          <span itemprop="price" content="2999">2999</span>
          <span itemprop="ratingValue">4.3</span>
          <span itemprop="reviewCount">87</span>
        </div>
        """
        outcome = _run_strategy(html)

        assert outcome.rating == 4.3
        assert outcome.review_count == 87


class TestNoReviewData:
    def test_returns_none_none_when_page_has_no_rating_signals(self):
        html = """
        <script type="application/ld+json">
        {"@type": "Product", "offers": {"price": "999"}}
        </script>
        """
        outcome = _run_strategy(html)

        assert outcome.rating is None
        assert outcome.review_count is None
