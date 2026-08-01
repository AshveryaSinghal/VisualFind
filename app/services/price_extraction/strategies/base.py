"""
Abstract base for every extraction strategy (Tier 1/2/3).

Adding a new tier later (e.g. a retailer-specific API, a browser-extension
relay, an OCR-on-screenshot fallback) means: subclass this, implement
`extract`, and add one line to PriceExtractionService's strategy list.
Nothing else in the pipeline needs to change.
"""

import logging
import time
from abc import ABC, abstractmethod

from app.services.price_extraction.types import StrategyOutcome

logger = logging.getLogger(__name__)

class ExtractionStrategy(ABC):

    name: str = "base"

    @abstractmethod
    def _run(self, **context) -> StrategyOutcome:
        """Subclasses implement the actual extraction logic here."""
        raise NotImplementedError

    def run(self, **context) -> StrategyOutcome:
        """
        Timed, exception-safe wrapper around `_run`. A strategy raising for
        any reason (network error, malformed HTML, missing dependency) is
        caught here and converted into a failed StrategyOutcome - it must
        never propagate and take down the rest of the pipeline or the
        product being processed.
        """
        start = time.perf_counter()
        try:
            outcome = self._run(**context)
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.warning(
                "Strategy Failed | strategy=%s error=%s time_ms=%.1f",
                self.name, e, elapsed_ms,
            )
            return StrategyOutcome(
                strategy_name=self.name,
                extraction_method="none",
                success=False,
                candidates=[],
                error=str(e),
                time_taken_ms=elapsed_ms,
            )

        outcome.time_taken_ms = (time.perf_counter() - start) * 1000
        return outcome
