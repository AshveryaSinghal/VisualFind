"""
Tier 2 - Structured page metadata.

Best-effort GET of the product page itself, then a scan for every kind of
structured price signal e-commerce sites commonly expose *without* needing
JavaScript execution:

  - JSON-LD (`<script type="application/ld+json">`) Product/Offer schema
  - schema.org microdata (`itemprop="price"` / `itemprop="lowPrice"` etc.)
  - OpenGraph product meta tags (`og:price:amount`, `product:price:amount`)
  - generic `<meta name="price" ...>` / `content` price tags
  - price-shaped values embedded in other inline `<script>` JSON blobs
    (e.g. Next.js `__NEXT_DATA__`, Shopify's product JSON, redux hydration
    state) - a broad but conservative regex scan for `"price"`-ish keys

While the page is already fetched and parsed for price signals, this tier
also opportunistically pulls rating/review-count data out of the same
JSON-LD (`Product.aggregateRating.ratingValue` / `.reviewCount` /
`.ratingCount`) and schema.org microdata (`itemprop="ratingValue"` /
`"reviewCount"` / `"ratingCount"`) - this is exposed on the vast majority of
product pages regardless of retailer, so it's a much broader source of
review data than Google Shopping alone (which only has listings for
platforms/products it happens to index). Surfaced on the StrategyOutcome
even when no usable price is found on the same page, so a later tier
winning on price doesn't throw away review data this tier already fetched.

Every candidate found is tagged with a role inferred from its surrounding
label so Tier 6 can later prefer the real selling price over MRP/EMI/etc.

Off by default toggle available (ENABLE_PAGE_METADATA_FALLBACK in config)
since this is the first tier that talks to the retailer directly and may be
blocked by bot detection - failures here are expected and handled silently
by the base class's exception-safe `run()` wrapper.
"""

import json
import re

import requests
from bs4 import BeautifulSoup

from app.config import settings
from app.services.price_extraction.strategies.base import ExtractionStrategy
from app.services.price_extraction.types import PriceCandidate, PriceRole, StrategyOutcome
from app.services.price_extraction.validation import infer_role_from_text
from app.services.price_utils import normalize_rating, normalize_review_count

_PAGE_FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; VisualFindBot/1.0; +https://example.com/bot)"
}

_JSON_PRICE_KEY_PATTERN = re.compile(
    r'"(sellingPrice|salePrice|offerPrice|finalPrice|currentPrice|discountedPrice|'
    r'price|lowPrice|mrp|listPrice|originalPrice)"\s*:\s*"?([\d,.]+)"?',
    re.IGNORECASE,
)

_JSON_KEY_ROLE = {
    "sellingprice": PriceRole.SELLING_PRICE,
    "saleprice": PriceRole.SELLING_PRICE,
    "offerprice": PriceRole.SELLING_PRICE,
    "finalprice": PriceRole.SELLING_PRICE,
    "currentprice": PriceRole.SELLING_PRICE,
    "discountedprice": PriceRole.SELLING_PRICE,
    "price": PriceRole.SELLING_PRICE,
    "lowprice": PriceRole.SELLING_PRICE,
    "mrp": PriceRole.LIST_PRICE,
    "listprice": PriceRole.LIST_PRICE,
    "originalprice": PriceRole.LIST_PRICE,
}

class StructuredMetadataStrategy(ExtractionStrategy):
    name = "structured_metadata"

    def _run(self, url: str | None = None, **_) -> StrategyOutcome:
        if not settings.enable_page_metadata_fallback:
            return StrategyOutcome(
                strategy_name=self.name,
                extraction_method="disabled",
                success=False,
                candidates=[],
                error="page metadata fallback disabled via config",
            )
        if not url:
            return StrategyOutcome(
                strategy_name=self.name,
                extraction_method="none",
                success=False,
                candidates=[],
                error="no url provided",
            )

        resp = requests.get(
            url,
            timeout=settings.page_metadata_fetch_timeout_seconds,
            headers=_PAGE_FETCH_HEADERS,
        )
        if resp.status_code != 200:
            return StrategyOutcome(
                strategy_name=self.name,
                extraction_method="none",
                success=False,
                candidates=[],
                error=f"HTTP {resp.status_code}",
            )

        soup = BeautifulSoup(resp.text, "html.parser")

        candidates: list[PriceCandidate] = []
        methods_hit: list[str] = []

        json_ld_nodes = self._parse_json_ld_nodes(soup)

        json_ld = self._extract_json_ld_prices(json_ld_nodes)
        if json_ld:
            candidates.extend(json_ld)
            methods_hit.append("json_ld")

        microdata = self._extract_microdata(soup)
        if microdata:
            candidates.extend(microdata)
            methods_hit.append("schema_org_microdata")

        opengraph = self._extract_opengraph(soup)
        if opengraph:
            candidates.extend(opengraph)
            methods_hit.append("opengraph")

        meta_tags = self._extract_meta_price_tags(soup)
        if meta_tags:
            candidates.extend(meta_tags)
            methods_hit.append("meta_tag")

        inline_json = self._extract_inline_script_json(soup)
        if inline_json:
            candidates.extend(inline_json)
            methods_hit.append("inline_script_json")

        rating, review_count = self._extract_rating_and_reviews(json_ld_nodes, soup)

        if not candidates:
            return StrategyOutcome(
                strategy_name=self.name,
                extraction_method="none",
                success=False,
                candidates=[],
                error="no structured price signals found",
                rating=rating,
                review_count=review_count,
            )

        return StrategyOutcome(
            strategy_name=self.name,
            extraction_method="+".join(methods_hit),
            success=True,
            candidates=candidates,
            rating=rating,
            review_count=review_count,
        )

    def _parse_json_ld_nodes(self, soup: BeautifulSoup) -> list[dict]:
        """Parses every JSON-LD script tag into a flat list of dict nodes (expanding @graph)."""
        nodes: list[dict] = []

        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            raw = script.string or script.get_text() or ""
            raw = raw.strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except (ValueError, TypeError):
                continue

            objects = data if isinstance(data, list) else [data]
            for obj in objects:
                nodes.extend(self._flatten_json_ld_object(obj))

        return nodes

    def _flatten_json_ld_object(self, obj) -> list[dict]:
        if not isinstance(obj, dict):
            return []
        if "@graph" in obj and isinstance(obj["@graph"], list):
            flattened = []
            for node in obj["@graph"]:
                flattened.extend(self._flatten_json_ld_object(node))
            return flattened
        return [obj]

    def _extract_json_ld_prices(self, json_ld_nodes: list[dict]) -> list[PriceCandidate]:
        found: list[PriceCandidate] = []
        for obj in json_ld_nodes:
            found.extend(self._offers_from_json_ld_object(obj))
        return found

    def _extract_rating_and_reviews(
        self, json_ld_nodes: list[dict], soup: BeautifulSoup
    ) -> tuple[float | None, int | None]:
        """
        Pulls `Product.aggregateRating.ratingValue`/`.reviewCount`/`.ratingCount`
        out of JSON-LD first (most reliable, least likely to be a decoy), then
        falls back to the equivalent schema.org microdata itemprops. Returns
        (None, None) if the page exposes neither - never raises, callers treat
        missing review data the same as missing price data.
        """
        rating: float | None = None
        review_count: int | None = None

        for obj in json_ld_nodes:
            aggregate = obj.get("aggregateRating")
            if not isinstance(aggregate, dict):
                continue

            if rating is None:
                rating = normalize_rating(aggregate.get("ratingValue"))
            if review_count is None:
                review_count = normalize_review_count(
                    aggregate.get("reviewCount") or aggregate.get("ratingCount")
                )

            if rating is not None and review_count is not None:
                return rating, review_count

        if rating is None:
            tag = soup.find(attrs={"itemprop": "ratingValue"})
            if tag is not None:
                rating = normalize_rating(tag.get("content") or tag.get_text(strip=True))

        if review_count is None:
            tag = soup.find(attrs={"itemprop": "reviewCount"}) or soup.find(
                attrs={"itemprop": "ratingCount"}
            )
            if tag is not None:
                review_count = normalize_review_count(tag.get("content") or tag.get_text(strip=True))

        return rating, review_count

    def _offers_from_json_ld_object(self, obj) -> list[PriceCandidate]:
        if not isinstance(obj, dict):
            return []

        if "@graph" in obj and isinstance(obj["@graph"], list):
            found = []
            for node in obj["@graph"]:
                found.extend(self._offers_from_json_ld_object(node))
            return found

        offers = obj.get("offers")
        if not offers:
            return []

        offer_list = offers if isinstance(offers, list) else [offers]
        found: list[PriceCandidate] = []
        for offer in offer_list:
            if not isinstance(offer, dict):
                continue
            price = offer.get("price") or offer.get("lowPrice")
            if not price:
                continue
            found.append(
                PriceCandidate(
                    raw_price=price,
                    raw_currency=offer.get("priceCurrency"),
                    role=PriceRole.SELLING_PRICE,
                    label="json_ld.offers.price",
                )
            )

            high_price = offer.get("highPrice")
            if high_price and high_price != price:
                found.append(
                    PriceCandidate(
                        raw_price=high_price,
                        raw_currency=offer.get("priceCurrency"),
                        role=PriceRole.LIST_PRICE,
                        label="json_ld.offers.highPrice",
                    )
                )
        return found

    def _extract_microdata(self, soup: BeautifulSoup) -> list[PriceCandidate]:
        found: list[PriceCandidate] = []

        for tag in soup.find_all(attrs={"itemprop": True}):
            itemprop = (tag.get("itemprop") or "").lower()
            if itemprop not in ("price", "lowprice", "highprice"):
                continue

            raw_value = tag.get("content") or tag.get_text(strip=True)
            if not raw_value:
                continue

            role = PriceRole.LIST_PRICE if itemprop == "highprice" else PriceRole.SELLING_PRICE

            currency_tag = tag.find_previous(attrs={"itemprop": "priceCurrency"}) or tag.find_next(
                attrs={"itemprop": "priceCurrency"}
            )
            raw_currency = None
            if currency_tag is not None:
                raw_currency = currency_tag.get("content") or currency_tag.get_text(strip=True)

            found.append(
                PriceCandidate(
                    raw_price=raw_value,
                    raw_currency=raw_currency,
                    role=role,
                    label=f"microdata.itemprop.{itemprop}",
                )
            )

        return found

    def _extract_opengraph(self, soup: BeautifulSoup) -> list[PriceCandidate]:
        found: list[PriceCandidate] = []
        amount = None
        currency = None

        for prop in ("og:price:amount", "product:price:amount"):
            tag = soup.find("meta", attrs={"property": prop})
            if tag and tag.get("content"):
                amount = tag["content"]
                break

        for prop in ("og:price:currency", "product:price:currency"):
            tag = soup.find("meta", attrs={"property": prop})
            if tag and tag.get("content"):
                currency = tag["content"]
                break

        if amount:
            found.append(
                PriceCandidate(
                    raw_price=amount,
                    raw_currency=currency,
                    role=PriceRole.SELLING_PRICE,
                    label="opengraph.price:amount",
                )
            )

        return found

    def _extract_meta_price_tags(self, soup: BeautifulSoup) -> list[PriceCandidate]:
        found: list[PriceCandidate] = []

        for name in ("price", "twitter:data1", "sailthru.price"):
            tag = soup.find("meta", attrs={"name": name})
            if tag and tag.get("content"):
                found.append(
                    PriceCandidate(
                        raw_price=tag["content"],
                        raw_currency=None,
                        role=infer_role_from_text(name, tag.get("content")),
                        label=f"meta.{name}",
                    )
                )

        return found

    def _extract_inline_script_json(self, soup: BeautifulSoup) -> list[PriceCandidate]:
        found: list[PriceCandidate] = []

        for script in soup.find_all("script"):
            if script.get("type") == "application/ld+json":
                continue
            text = script.string or ""
            if not text or "price" not in text.lower():
                continue

            snippet = text[:200_000]
            for match in _JSON_PRICE_KEY_PATTERN.finditer(snippet):
                key, value = match.group(1), match.group(2)
                role = _JSON_KEY_ROLE.get(key.lower(), PriceRole.UNKNOWN)
                found.append(
                    PriceCandidate(
                        raw_price=value,
                        raw_currency=None,
                        role=role,
                        label=f"inline_script_json.{key}",
                    )
                )
                if len(found) >= 20:
                    break
            if len(found) >= 20:
                break

        return found
