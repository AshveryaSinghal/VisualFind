"""
Structured per-attempt logging for the extraction pipeline.

One line per strategy attempt, in the same `key=value` style as the rest of
the codebase's logging (see search_service.py / price_service.py), so these
interleave cleanly in the same log stream. Deliberately includes everything
requested for observability: platform, URL, strategy, time taken,
success/failure, detected price, and confidence.
"""

import logging

logger = logging.getLogger(__name__)

def log_attempt(
    *,
    platform: str | None,
    url: str | None,
    strategy_name: str,
    time_taken_ms: float,
    success: bool,
    detected_price: object = None,
    confidence: float | None = None,
    error: str | None = None,
) -> None:
    status = "SUCCESS" if success else "FAILURE"
    if success:
        logger.info(
            "Price Extraction Attempt | platform=%s url=%s strategy=%s time_ms=%.1f status=%s price=%s confidence=%s",
            platform, url, strategy_name, time_taken_ms, status, detected_price, confidence,
        )
    else:
        logger.info(
            "Price Extraction Attempt | platform=%s url=%s strategy=%s time_ms=%.1f status=%s reason=%s",
            platform, url, strategy_name, time_taken_ms, status, error,
        )

def log_final_result(
    *,
    platform: str | None,
    url: str | None,
    price: float | None,
    currency: str | None,
    price_source: str,
    extraction_method: str,
    confidence_score: float,
) -> None:
    logger.info(
        "Price Extraction Result | platform=%s url=%s price_source=%s extraction_method=%s "
        "price=%s currency=%s confidence=%.2f",
        platform, url, price_source, extraction_method, price, currency, confidence_score,
    )
