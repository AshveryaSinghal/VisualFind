"""
Bonus strategy (runs between Tier 1 and Tier 2) - reuse price data Google
Lens already returned alongside the candidate purchase link, instead of
making another network call for something we already have in hand.

Not one of the seven required pipeline stages, but demonstrates the
"additional strategies can be added later" extensibility the orchestrator
was built for, and preserves data the app already surfaced before this
pipeline existed.
"""

from app.services.price_extraction.strategies.base import ExtractionStrategy
from app.services.price_extraction.types import PriceCandidate, PriceRole, StrategyOutcome

class LensCandidateStrategy(ExtractionStrategy):
    name = "lens"

    def _run(self, candidate: dict | None = None, **_) -> StrategyOutcome:
        candidate = candidate or {}
        price = candidate.get("price")
        if price is None:
            return StrategyOutcome(
                strategy_name=self.name,
                extraction_method="lens_inline_price",
                success=False,
                candidates=[],
                error="lens candidate had no price field",
            )

        return StrategyOutcome(
            strategy_name=self.name,
            extraction_method="lens_inline_price",
            success=True,
            candidates=[
                PriceCandidate(
                    raw_price=price,
                    raw_currency=candidate.get("currency"),
                    role=PriceRole.SELLING_PRICE,
                    label="lens.price",
                )
            ],
        )
