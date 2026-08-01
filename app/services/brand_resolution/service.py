"""
BrandResolutionService - the only entry point search_service.py needs to
know about for brand-related work. Keeps every brand concern (detection,
domain resolution, official-site scraping, and their logging) out of
search_service.py and domain_filter.py entirely, matching the same
"orchestrator wraps tiers" shape as price_service.py / PriceExtractionService.

Pipeline:
  1. BrandDetector          - multi-signal brand detection + confidence
  2. BrandDomainResolver    - official domain for the winning brand
  3. OfficialSiteSearchStrategy - find + scrape the product on that domain

Brand Verification: if multiple brands are detected, only the
highest-confidence one is used (BrandDetector already ranks and returns the
winner). If confidence is too low to act on, official-site resolution is
skipped entirely and the existing marketplace pipeline continues unaffected
- this service is additive, and its failure (at any tier, for any reason)
never raises and never blocks the rest of the search.
"""

import logging
import time

from app.config import settings
from app.services.brand_resolution.detector import BrandDetector
from app.services.brand_resolution.logging_utils import (
    log_detected_brand,
    log_domain_resolution_skipped,
    log_official_domain,
    log_official_product_found,
    log_official_search_failed,
    log_official_search_started,
)
from app.services.brand_resolution.official_site_search import OfficialSiteSearchStrategy
from app.services.brand_resolution.resolver import BrandDomainResolver
from app.services.brand_resolution.types import BrandResolutionResult, OfficialProduct

logger = logging.getLogger(__name__)

class BrandResolutionService:
    def __init__(self):
        self._detector = BrandDetector()
        self._domain_resolver = BrandDomainResolver()
        self._official_search = OfficialSiteSearchStrategy()

    def resolve(
        self,
        lens_response: dict,
        candidates: list[dict],
        query: str | None,
        offers: list[dict] | None = None,
    ) -> BrandResolutionResult:
        start = time.perf_counter()

        if not settings.enable_brand_resolution:
            return BrandResolutionResult(detected_brand=None, brand_confidence=0.0)

        try:
            return self._resolve(lens_response, candidates, query, offers, start)
        except Exception as e:
            logger.warning("Brand resolution pipeline failed unexpectedly: %s", e)
            return BrandResolutionResult(
                detected_brand=None,
                brand_confidence=0.0,
                search_time_ms=(time.perf_counter() - start) * 1000,
            )

    def _resolve(
        self,
        lens_response: dict,
        candidates: list[dict],
        query: str | None,
        offers: list[dict] | None,
        start: float,
    ) -> BrandResolutionResult:
        detection = self._detector.detect(
            lens_response=lens_response,
            candidates=candidates,
            query=query,
            offers=offers,
            enable_page_metadata_lookup=settings.enable_brand_page_metadata_lookup,
        )
        log_detected_brand(detection.brand, detection.confidence)

        if not detection.brand or detection.confidence < settings.min_brand_confidence_for_domain_resolution:

            if detection.brand:
                log_domain_resolution_skipped(
                    detection.brand, detection.confidence, settings.min_brand_confidence_for_domain_resolution
                )
            return BrandResolutionResult(
                detected_brand=detection.brand,
                brand_confidence=detection.confidence,
                search_time_ms=(time.perf_counter() - start) * 1000,
            )

        domain, domain_source, _domain_confidence = self._domain_resolver.resolve(detection.brand, candidates)
        log_official_domain(domain, domain_source)

        if not domain:
            log_official_search_failed(None, "no official domain could be resolved")
            return BrandResolutionResult(
                detected_brand=detection.brand,
                brand_confidence=detection.confidence,
                search_time_ms=(time.perf_counter() - start) * 1000,
            )

        search_query = query or detection.brand
        log_official_search_started(domain, search_query)

        official_product = self._official_search.search(
            domain=domain,
            query=search_query,
            brand_name=detection.brand,
            timeout_seconds=settings.brand_search_timeout_seconds,
        )

        if official_product is not None:
            log_official_product_found(domain, official_product.title, official_product.price, official_product.currency)
        else:
            # The scrape/site-search tier can fail for lots of harmless reasons
            # (no JSON-LD/OpenGraph on the page, site-search turned up nothing,
            # request timed out) even though we *do* know the brand's official
            # domain. Showing "no official store" in that case is wrong - a
            # known official domain must always surface a link, even if it's
            # just the homepage rather than the exact product page.
            official_product = _fallback_official_product(domain, detection.brand)
            log_official_product_found(domain, official_product.title, official_product.price, official_product.currency)

        return BrandResolutionResult(
            detected_brand=detection.brand,
            brand_confidence=detection.confidence,
            official_domain=domain,
            official_domain_source=domain_source,
            official_product=official_product,
            search_time_ms=(time.perf_counter() - start) * 1000,
        )

def _fallback_official_product(domain: str, brand_name: str | None) -> OfficialProduct:
    """Last-resort OfficialProduct used when we know the brand's official
    domain but couldn't locate/scrape the specific product page on it.

    Mandatory-display guarantee: once a domain has been resolved for a
    detected brand, the official store must always appear in results - even
    for brands outside the marketplace allowlist (TRUSTED_DOMAINS) - rather
    than silently disappearing because the page scrape happened to fail.
    Links to the site's homepage since that's the one URL guaranteed to
    exist and to be genuinely official.
    """
    title = f"{brand_name} Official Store" if brand_name else "Official Website"
    return OfficialProduct(
        platform="Official Website",
        title=title,
        link=f"https://{domain}",
        source_domain=domain,
        price_source="official_website",
        extraction_method="fallback_homepage",
        confidence_score=0.4,
    )

def official_product_to_merge_dict(product: OfficialProduct, brand_name: str | None) -> dict:
    """
    Converts an OfficialProduct into the same plain-dict shape
    price_service.enrich_with_live_prices produces for marketplace
    candidates, so search_service can merge it through the existing
    dedupe/sort/best-deal pipeline (price_utils.py) unmodified.
    """
    label = f"{brand_name} Official Store" if brand_name else "Official Website"
    return {
        "platform": label,
        "title": product.title,
        "price": product.price,
        "currency": product.currency,
        "link": product.link,
        "source_domain": product.source_domain,
        "thumbnail": product.thumbnail,
        "rating": product.rating,
        "review_count": product.review_count,
        "price_source": product.price_source,
        "extraction_method": product.extraction_method,
        "confidence_score": product.confidence_score,
    }
