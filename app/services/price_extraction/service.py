"""
PriceExtractionService - orchestrates the full multi-stage price extraction
pipeline for a single product candidate.

  Tier 1  GoogleShoppingStrategy    - live SerpAPI Google Shopping offers
  (1.5)   LensCandidateStrategy     - reuse price Google Lens already gave us
  Tier 2  StructuredMetadataStrategy- JSON-LD / microdata / OpenGraph / meta
  Tier 3  HeadlessBrowserStrategy   - rendered-DOM fallback (Playwright)
  Tier 4  normalization             - currency/number normalization
  Tier 5  validation                - reject implausible/non-selling prices
  Tier 6  selection                 - choose the real selling price
  Tier 7  this class's return value - price/currency/price_source/
                                       confidence_score/extraction_method

Strategies run **in order** and the pipeline stops at the first one that
yields a valid, plausible selling price - later tiers are strictly more
expensive (network round trip, then a full browser render), so there's no
reason to pay that cost once an earlier tier already answered the question.

Every strategy failure - network error, missing dependency, malformed page,
no data found - is caught, logged, and treated as "try the next tier". A
single product failing every tier returns a null-price ExtractionResult; it
never raises, and it never stops the caller from processing the rest of the
batch (see price_service.py, which calls this once per candidate inside its
own try/except as a second line of defense).
"""

import logging

from app.services.price_extraction.logging_utils import log_attempt, log_final_result
from app.services.price_extraction.normalization import normalize_candidates
from app.services.price_extraction.selection import select_best_candidate
from app.services.price_extraction.strategies.google_shopping import GoogleShoppingStrategy
from app.services.price_extraction.strategies.headless_browser import HeadlessBrowserStrategy
from app.services.price_extraction.strategies.lens_candidate import LensCandidateStrategy
from app.services.price_extraction.strategies.structured_metadata import StructuredMetadataStrategy
from app.services.price_extraction.types import ExtractionResult
from app.services.price_extraction.validation import filter_valid_candidates

logger = logging.getLogger(__name__)

_BASE_CONFIDENCE = {
    "google_shopping": 0.95,
    "lens": 0.80,
    "structured_metadata": 0.70,
    "headless_browser": 0.55,
}

_METHOD_CONFIDENCE_ADJUSTMENT = {
    "json_ld": +0.05,
    "schema_org_microdata": +0.03,
    "opengraph": 0.0,
    "meta_tag": -0.05,
    "inline_script_json": -0.10,
    "rendered_dom": 0.0,
}

class PriceExtractionService:
    """
    Stateless orchestrator - safe to instantiate once and reuse (or
    construct fresh per call, it holds no per-request state itself).
    """

    def __init__(self, strategies: list | None = None):

        self.strategies = strategies or [
            GoogleShoppingStrategy(),
            LensCandidateStrategy(),
            StructuredMetadataStrategy(),
            HeadlessBrowserStrategy(),
        ]

    def extract(
        self,
        candidate: dict,
        offers_by_platform: dict | None = None,
    ) -> ExtractionResult:
        """
        `candidate` is a trusted-platform product dict (must have `link` and
        `platform`; may already have `price`/`currency` from Google Lens).
        `offers_by_platform` is the pre-fetched bulk Google Shopping result,
        keyed by platform display name (see price_service.fetch_offers_for_query).
        """
        platform = candidate.get("platform")
        url = candidate.get("link")

        rating: float | None = None
        review_count: int | None = None

        for strategy in self.strategies:
            outcome = strategy.run(
                url=url,
                platform=platform,
                offers_by_platform=offers_by_platform,
                candidate=candidate,
            )

            if rating is None and outcome.rating is not None:
                rating = outcome.rating
            if review_count is None and outcome.review_count is not None:
                review_count = outcome.review_count

            if not outcome.success:
                log_attempt(
                    platform=platform,
                    url=url,
                    strategy_name=strategy.name,
                    time_taken_ms=outcome.time_taken_ms,
                    success=False,
                    error=outcome.error,
                )
                continue

            normalized = normalize_candidates(outcome.candidates, reference_url=url, platform=platform)
            valid = filter_valid_candidates(normalized)

            if not valid:
                log_attempt(
                    platform=platform,
                    url=url,
                    strategy_name=strategy.name,
                    time_taken_ms=outcome.time_taken_ms,
                    success=False,
                    error="candidate price(s) found but rejected by validation",
                )
                continue

            chosen = select_best_candidate(valid)
            confidence = self._confidence(strategy.name, outcome.extraction_method)

            log_attempt(
                platform=platform,
                url=url,
                strategy_name=strategy.name,
                time_taken_ms=outcome.time_taken_ms,
                success=True,
                detected_price=chosen.value,
                confidence=confidence,
            )

            result = ExtractionResult(
                price=chosen.value,
                currency=chosen.currency,
                price_source=strategy.name,
                extraction_method=outcome.extraction_method,
                confidence_score=confidence,
                raw_price=chosen.value,
                rating=rating,
                review_count=review_count,
            )
            log_final_result(
                platform=platform,
                url=url,
                price=result.price,
                currency=result.currency,
                price_source=result.price_source,
                extraction_method=result.extraction_method,
                confidence_score=result.confidence_score,
            )
            return result

        result = ExtractionResult(
            price=None,
            currency=None,
            price_source="unavailable",
            extraction_method="none",
            confidence_score=0.0,
            rating=rating,
            review_count=review_count,
        )
        log_final_result(
            platform=platform,
            url=url,
            price=None,
            currency=None,
            price_source=result.price_source,
            extraction_method=result.extraction_method,
            confidence_score=result.confidence_score,
        )
        return result

    @staticmethod
    def _confidence(strategy_name: str, extraction_method: str) -> float:
        base = _BASE_CONFIDENCE.get(strategy_name, 0.5)

        adjustment = 0.0
        for method_key, delta in _METHOD_CONFIDENCE_ADJUSTMENT.items():
            if method_key in extraction_method:
                adjustment = max(adjustment, delta) if delta >= 0 else min(adjustment, delta)
        score = base + adjustment
        return round(max(0.0, min(score, 0.99)), 2)
