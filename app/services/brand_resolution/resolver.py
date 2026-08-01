"""
Tier 2 - BrandDomainResolver.

Resolves the official website domain for an already-detected brand name.
Modular by design: each strategy is a small method tried in cheapest-first
order, and adding a new strategy later means adding one method and one
entry to `_STRATEGIES` - nothing else changes.

Strategy order:
  1. Local brand-domain map          (domain_map.py)        - free, instant
  2. Existing candidate-link metadata (a Lens/Shopping link already on a
     domain that looks like the brand's own site)            - free
  3. Trusted web search               ("<brand> official website")
     - the only strategy that costs a network call, and the only one whose
       result must be filtered against known non-official domains
       (marketplaces, social media, wikis - see domain_map.py).

Every strategy returns (domain, source_name, confidence) or None; the first
one that succeeds wins.
"""

import logging
from urllib.parse import urlparse

from app.services.brand_resolution.domain_map import NON_OFFICIAL_DOMAIN_FRAGMENTS, lookup_domain
from app.services.domain_filter import TRUSTED_DOMAINS
from app.services.serpapi_client import SerpApiError, extract_organic_results, google_web_search

logger = logging.getLogger(__name__)

_MARKETPLACE_DOMAIN_FRAGMENTS = tuple(TRUSTED_DOMAINS.keys())

def _root_domain(netloc: str) -> str:
    netloc = netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc

def _is_disqualified(netloc: str) -> bool:
    return any(frag in netloc for frag in NON_OFFICIAL_DOMAIN_FRAGMENTS) or any(
        frag in netloc for frag in _MARKETPLACE_DOMAIN_FRAGMENTS
    )

class BrandDomainResolver:
    def resolve(self, brand_name: str, candidates: list[dict] | None = None) -> tuple[str | None, str | None, float]:
        """Returns (domain, source, confidence). domain is None if every
        strategy failed - the caller treats that as "skip official search",
        never as an error."""
        for strategy in (self._from_local_map, self._from_candidate_links, self._from_trusted_search):
            result = strategy(brand_name, candidates or [])
            if result is not None:
                return result
        return None, None, 0.0

    def _from_local_map(self, brand_name: str, candidates: list[dict]) -> tuple[str, str, float] | None:
        domain = lookup_domain(brand_name)
        if domain:
            return domain, "local_domain_map", 0.99
        return None

    def _from_candidate_links(self, brand_name: str, candidates: list[dict]) -> tuple[str, str, float] | None:
        """If a Lens/Shopping candidate link's domain already loosely
        matches the brand name and isn't a known marketplace/social/wiki
        domain, that's a reasonable signal it *is* the brand's own site."""
        brand_key = brand_name.lower().replace(" ", "")
        for candidate in candidates:
            link = candidate.get("link")
            if not link:
                continue
            try:
                netloc = _root_domain(urlparse(link).netloc)
            except Exception:
                continue
            if not netloc or _is_disqualified(netloc):
                continue
            domain_base = netloc.split(".")[0]
            if brand_key and (brand_key in domain_base or domain_base in brand_key):
                return netloc, "existing_candidate_metadata", 0.8
        return None

    def _from_trusted_search(self, brand_name: str, candidates: list[dict]) -> tuple[str, str, float] | None:
        try:
            response = google_web_search(f"{brand_name} official website")
            results = extract_organic_results(response)
        except SerpApiError as e:
            logger.info("Brand domain trusted-search failed | brand=%s error=%s", brand_name, e)
            return None

        for result in results[:5]:
            try:
                netloc = _root_domain(urlparse(result["link"]).netloc)
            except Exception:
                continue
            if not netloc or _is_disqualified(netloc):
                continue
            return netloc, "trusted_search", 0.55

        return None
