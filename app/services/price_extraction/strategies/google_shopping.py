"""
Tier 1 - Google Shopping (via SerpAPI).

Cheapest and most authoritative source when it has data: SerpApi has
already licensed this pricing from the retailers, so there's no scraping
risk and no bot-detection to fight. If it returns a valid numeric price for
the candidate's platform, the pipeline stops right here - no need to fall
through to slower/less reliable tiers.

This strategy is deliberately "dumb" about fetching: the actual SerpApi
call is a bulk, per-query operation shared across every candidate product
(one Shopping search covers all platforms), so the caller (PriceExtractionService)
fetches `offers_by_platform` once per search and passes the relevant slice
in via context - this class just picks the cheapest valid offer out of it.
"""

from app.services.price_extraction.strategies.base import ExtractionStrategy
from app.services.price_extraction.types import PriceCandidate, PriceRole, StrategyOutcome
from app.services.price_utils import extract_numeric_price, normalize_rating, normalize_review_count

class GoogleShoppingStrategy(ExtractionStrategy):
    name = "google_shopping"

    def _run(self, platform: str | None = None, offers_by_platform: dict | None = None, **_) -> StrategyOutcome:
        offers_by_platform = offers_by_platform or {}
        offers = offers_by_platform.get(platform, []) if platform else []

        priced_offers = [o for o in offers if extract_numeric_price(o.get("price")) is not None]
        if not priced_offers:
            return StrategyOutcome(
                strategy_name=self.name,
                extraction_method="serpapi_google_shopping",
                success=False,
                candidates=[],
                error="no priced offers for platform",
            )

        best_offer = min(priced_offers, key=lambda o: extract_numeric_price(o["price"]))

        candidate = PriceCandidate(
            raw_price=best_offer["price"],
            raw_currency=best_offer.get("currency"),
            role=PriceRole.SELLING_PRICE,
            label="google_shopping.price",
            context=best_offer.get("title"),
        )

        return StrategyOutcome(
            strategy_name=self.name,
            extraction_method="serpapi_google_shopping",
            success=True,
            candidates=[candidate],
            rating=normalize_rating(best_offer.get("rating")),
            review_count=normalize_review_count(best_offer.get("reviews")),
        )
