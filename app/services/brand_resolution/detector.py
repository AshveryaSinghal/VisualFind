"""
Tier 1 - Brand Detection.

Never trusts a single source: pulls brand-name hints from every signal the
app already has lying around after a Lens + Shopping round-trip, scores each
one, and combines corroborating signals into a per-brand confidence score.

Signal sources consulted (see BrandSignalSource in types.py):
  - Google Lens knowledge_graph / best-guess label
  - Google Shopping merchant/source names
  - Product titles (both a known-brand substring match and a generic
    "first capitalized word" heuristic)
  - The product URL's domain (a very strong signal if that domain is
    already a known brand's own site)
  - Optional structured-metadata pass (JSON-LD `brand`, OpenGraph, a
    `manufacturer` field) on the top candidate's page - only run when the
    cheap signals above didn't already produce a confident answer, since
    it's the only signal here that costs a network round trip.

Combining signals: for a given brand name, confidence is
`1 - product(1 - weight_i)` across every supporting signal - this saturates
toward 1.0 as more independent signals agree, without letting any single
weak signal alone claim high confidence.
"""

import json
import logging
import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from app.services.brand_resolution.domain_map import BRAND_DOMAIN_MAP
from app.services.brand_resolution.types import (
    BrandCandidate,
    BrandDetectionResult,
    BrandSignal,
    BrandSignalSource,
)

logger = logging.getLogger(__name__)

_PAGE_FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; VisualFindBot/1.0; +https://example.com/bot)"
}
_PAGE_FETCH_TIMEOUT_SECONDS = 4.0

_TITLE_HEURISTIC_STOPWORDS = {
    "the", "new", "best", "original", "genuine", "combo", "pack", "set",
    "for", "with", "and", "buy", "online", "premium", "pure",
}

_LENS_BUCKETS = ("products", "exact_matches", "visual_matches")

def _canonical(name: str) -> str:
    return " ".join(name.strip().split())

class BrandDetector:
    """Stateless - safe to reuse across requests."""

    def detect(
        self,
        lens_response: dict,
        candidates: list[dict],
        query: str | None,
        offers: list[dict] | None = None,
        enable_page_metadata_lookup: bool = True,
    ) -> BrandDetectionResult:
        signals: list[BrandSignal] = []

        signals.extend(self._from_knowledge_graph(lens_response))
        signals.extend(self._from_lens_best_guess(lens_response))
        signals.extend(self._from_lens_buckets(lens_response))
        signals.extend(self._from_titles(candidates, query))
        signals.extend(self._from_urls(candidates))
        signals.extend(self._from_shopping_offers(offers or []))

        ranked = self._rank(signals)

        if enable_page_metadata_lookup and (not ranked or ranked[0].confidence < 0.6):
            top_url = candidates[0]["link"] if candidates else None
            page_signals = self._from_structured_metadata(top_url)
            if page_signals:
                signals.extend(page_signals)
                ranked = self._rank(signals)

        if not ranked:
            return BrandDetectionResult(brand=None, confidence=0.0, ranked_candidates=[])

        best = ranked[0]
        return BrandDetectionResult(brand=best.name, confidence=best.confidence, ranked_candidates=ranked)

    def _from_knowledge_graph(self, lens_response: dict) -> list[BrandSignal]:
        kg = lens_response.get("knowledge_graph") or {}
        title = kg.get("title")
        if not title:
            return []
        return self._brand_signals_from_text(title, BrandSignalSource.KNOWLEDGE_GRAPH, base_weight=0.55)

    def _from_lens_best_guess(self, lens_response: dict) -> list[BrandSignal]:
        query_displayed = (lens_response.get("search_information") or {}).get("query_displayed")
        if not query_displayed:
            return []
        return self._brand_signals_from_text(query_displayed, BrandSignalSource.LENS_BEST_GUESS, base_weight=0.5)

    def _from_lens_buckets(self, lens_response: dict) -> list[BrandSignal]:
        """Lens items sometimes carry a `source` (merchant) field alongside
        title/link - a cheap extra signal we don't otherwise extract."""
        signals: list[BrandSignal] = []
        for bucket in _LENS_BUCKETS:
            for item in (lens_response.get(bucket) or [])[:5]:
                source = item.get("source")
                if source:
                    signals.extend(
                        self._brand_signals_from_text(
                            source, BrandSignalSource.MERCHANT_NAME, base_weight=0.4
                        )
                    )
                manufacturer = item.get("manufacturer")
                if manufacturer:
                    signals.append(
                        BrandSignal(
                            brand_name=_canonical(str(manufacturer)),
                            source=BrandSignalSource.STRUCTURED_MANUFACTURER,
                            weight=0.9,
                            raw_value=str(manufacturer),
                        )
                    )
        return signals

    def _from_titles(self, candidates: list[dict], query: str | None) -> list[BrandSignal]:
        signals: list[BrandSignal] = []
        titles = [c.get("title") for c in candidates[:8] if c.get("title")]
        if query:
            titles.append(query)

        for title in titles:
            signals.extend(
                self._brand_signals_from_text(title, BrandSignalSource.PRODUCT_TITLE, base_weight=0.6)
            )

            words = title.split()
            if words:
                first = re.sub(r"[^A-Za-z0-9&]", "", words[0])
                if len(first) >= 3 and first.lower() not in _TITLE_HEURISTIC_STOPWORDS and first[0].isupper():
                    signals.append(
                        BrandSignal(
                            brand_name=_canonical(first),
                            source=BrandSignalSource.PRODUCT_TITLE_KEYWORD,
                            weight=0.3,
                            raw_value=title,
                        )
                    )
        return signals

    def _from_urls(self, candidates: list[dict]) -> list[BrandSignal]:
        """If a candidate's link is already hosted on a domain we recognize
        as some brand's own site, that's a very strong, essentially free signal."""
        signals: list[BrandSignal] = []
        reverse_map = {domain: brand for brand, domain in BRAND_DOMAIN_MAP.items()}

        for candidate in candidates[:10]:
            link = candidate.get("link")
            if not link:
                continue
            try:
                netloc = urlparse(link).netloc.lower().lstrip("www.")
            except Exception:
                continue
            for domain, brand in reverse_map.items():
                if domain in netloc:
                    signals.append(
                        BrandSignal(
                            brand_name=_canonical(brand),
                            source=BrandSignalSource.PRODUCT_URL_DOMAIN,
                            weight=0.9,
                            raw_value=link,
                        )
                    )
        return signals

    def _from_shopping_offers(self, offers: list[dict]) -> list[BrandSignal]:
        signals: list[BrandSignal] = []
        for offer in offers[:10]:
            source = offer.get("source")
            if source:
                signals.extend(
                    self._brand_signals_from_text(
                        source, BrandSignalSource.GOOGLE_SHOPPING_MERCHANT, base_weight=0.35
                    )
                )
        return signals

    def _from_structured_metadata(self, url: str | None) -> list[BrandSignal]:
        """Optional, more expensive pass: fetch the top candidate's page and
        look for JSON-LD `brand`/`manufacturer` and OpenGraph brand tags."""
        if not url:
            return []
        try:
            resp = requests.get(url, timeout=_PAGE_FETCH_TIMEOUT_SECONDS, headers=_PAGE_FETCH_HEADERS)
            if resp.status_code != 200:
                return []
            soup = BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            logger.info("Brand metadata page fetch failed | url=%s error=%s", url, e)
            return []

        signals: list[BrandSignal] = []

        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw = (script.string or script.get_text() or "").strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except (ValueError, TypeError):
                continue
            objects = data if isinstance(data, list) else [data]
            for obj in objects:
                if not isinstance(obj, dict):
                    continue
                brand = obj.get("brand")
                brand_name = None
                if isinstance(brand, dict):
                    brand_name = brand.get("name")
                elif isinstance(brand, str):
                    brand_name = brand
                if brand_name:
                    signals.append(
                        BrandSignal(
                            brand_name=_canonical(brand_name),
                            source=BrandSignalSource.JSON_LD_BRAND,
                            weight=0.95,
                            raw_value=brand_name,
                        )
                    )
                manufacturer = obj.get("manufacturer")
                if isinstance(manufacturer, dict) and manufacturer.get("name"):
                    signals.append(
                        BrandSignal(
                            brand_name=_canonical(manufacturer["name"]),
                            source=BrandSignalSource.STRUCTURED_MANUFACTURER,
                            weight=0.9,
                            raw_value=manufacturer["name"],
                        )
                    )

        og_brand = soup.find("meta", attrs={"property": "product:brand"}) or soup.find(
            "meta", attrs={"property": "og:brand"}
        )
        if og_brand and og_brand.get("content"):
            signals.append(
                BrandSignal(
                    brand_name=_canonical(og_brand["content"]),
                    source=BrandSignalSource.OPENGRAPH_BRAND,
                    weight=0.85,
                    raw_value=og_brand["content"],
                )
            )

        return signals

    def _brand_signals_from_text(
        self, text: str, source: BrandSignalSource, base_weight: float
    ) -> list[BrandSignal]:
        """Checks free text against the known-brand map (substring match) -
        a text signal is only as good as whether it actually names a brand
        we can recognize, so unmatched text produces no signal here (the
        title-heuristic path in _from_titles handles the "unknown brand"
        case separately, at lower weight)."""
        if not text:
            return []
        lowered = text.lower()
        signals = []
        for brand_key in BRAND_DOMAIN_MAP:
            if brand_key in lowered:
                signals.append(
                    BrandSignal(brand_name=_canonical(brand_key), source=source, weight=base_weight, raw_value=text)
                )
        return signals

    def _rank(self, signals: list[BrandSignal]) -> list[BrandCandidate]:
        grouped: dict[str, list[BrandSignal]] = {}
        for signal in signals:
            key = signal.brand_name.lower()
            grouped.setdefault(key, []).append(signal)

        candidates = []
        for _, group_signals in grouped.items():
            confidence = 1.0
            for signal in group_signals:
                confidence *= (1.0 - signal.weight)
            confidence = round(1.0 - confidence, 3)
            display_name = group_signals[0].brand_name
            candidates.append(BrandCandidate(name=display_name, confidence=confidence, signals=group_signals))

        return sorted(candidates, key=lambda c: c.confidence, reverse=True)
