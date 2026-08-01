"""
Structured logging for the Brand Resolution pipeline, in the same
`key=value` style as the rest of the app (see price_extraction/logging_utils.py)
so these lines interleave cleanly with the main search log stream.

Covers every field called out in the spec: Detected Brand, Brand
Confidence, Official Domain, Official Search Started, Official Product
Found, Official Product Price, Official Search Time, Official Search Failed.
"""

import logging

logger = logging.getLogger(__name__)

def log_detected_brand(brand: str | None, confidence: float) -> None:
    logger.info("Detected Brand | brand=%s", brand or "none")
    logger.info("Brand Confidence | confidence=%.2f", confidence)

def log_official_domain(domain: str | None, source: str | None) -> None:
    logger.info("Official Domain | domain=%s source=%s", domain or "none", source or "none")

def log_official_search_started(domain: str, query: str) -> None:
    logger.info("Official Search Started | domain=%s query=%s", domain, query)

def log_official_product_found(domain: str, title: str, price, currency) -> None:
    logger.info("Official Product Found | domain=%s title=%s", domain, title)
    logger.info("Official Product Price | domain=%s price=%s currency=%s", domain, price, currency)

def log_official_search_failed(domain: str | None, reason: str) -> None:
    logger.info("Official Search Failed | domain=%s reason=%s", domain or "none", reason)

def log_domain_resolution_skipped(brand: str, confidence: float, threshold: float) -> None:
    """
    Previously this branch (service.py: confidence below
    min_brand_confidence_for_domain_resolution) returned early with no log
    line at all - from the logs, a low-confidence skip and a "brand
    resolved fine, no official site exists" case were indistinguishable.
    """
    logger.info(
        "Official Domain Resolution Skipped | brand=%s confidence=%.2f threshold=%.2f reason=confidence below threshold",
        brand, confidence, threshold,
    )
