"""
Tier 3 - OfficialSiteSearchStrategy.

Given a resolved official domain and the product query, finds the specific
product page on that domain and extracts a trusted product record from it.

Two steps, each independently failure-safe:
  1. Locate the product page: a `site:<domain> <query>` web search, taking
     the first organic result whose link actually lives on that domain.
  2. Scrape that page for structured data (JSON-LD Product schema first,
     OpenGraph as a fallback) - the same signal types
     price_extraction/strategies/structured_metadata.py already trusts for
     price, reused here for the full product record (name, image, price,
     currency, rating, review count, availability, variants).

The official website is a trusted first-party source, so unlike the
marketplace pipeline there's no allowlist check here - reaching this class
at all already means the domain was resolved as the brand's own site.
"""

import json
import logging
import time

from bs4 import BeautifulSoup
import requests

from app.services.brand_resolution.types import OfficialProduct
from app.services.currency_resolver import currency_resolver
from app.services.price_extraction.validation import is_plausible_amount
from app.services.price_utils import extract_numeric_price
from app.services.serpapi_client import SerpApiError, extract_organic_results, google_web_search

logger = logging.getLogger(__name__)

_PAGE_FETCH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; VisualFindBot/1.0; +https://example.com/bot)"
}

class OfficialSiteSearchStrategy:
    def search(self, domain: str, query: str, brand_name: str, timeout_seconds: float = 6.0) -> OfficialProduct | None:
        start = time.perf_counter()
        try:
            product_url = self._find_product_url(domain, query, timeout_seconds)
            if not product_url:
                logger.info("Official Search Failed | domain=%s reason=no matching page found", domain)
                return None

            product = self._scrape_product(product_url, domain, brand_name, timeout_seconds)
            if product is None:
                logger.info("Official Search Failed | domain=%s reason=no structured product data on page", domain)
            return product
        except Exception as e:
            logger.info("Official Search Failed | domain=%s error=%s", domain, e)
            return None
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info("Official Search Time | domain=%s time_ms=%.1f", domain, elapsed_ms)

    def _find_product_url(self, domain: str, query: str, timeout_seconds: float) -> str | None:
        try:
            response = google_web_search(f"site:{domain} {query}")
            results = extract_organic_results(response)
        except SerpApiError as e:
            logger.info("Official product-page search failed | domain=%s error=%s", domain, e)
            return None

        for result in results:
            link = result.get("link") or ""
            if domain in link:
                return link
        return None

    def _scrape_product(
        self, url: str, domain: str, brand_name: str, timeout_seconds: float
    ) -> OfficialProduct | None:
        resp = requests.get(url, timeout=timeout_seconds, headers=_PAGE_FETCH_HEADERS)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        product = self._from_json_ld(soup, url, domain)
        if product is not None:
            return product

        return self._from_opengraph(soup, url, domain, brand_name)

    def _from_json_ld(self, soup: BeautifulSoup, url: str, domain: str) -> OfficialProduct | None:
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
                product = self._product_from_json_ld_object(obj, url, domain)
                if product is not None:
                    return product
        return None

    def _product_from_json_ld_object(self, obj, url: str, domain: str) -> OfficialProduct | None:
        if not isinstance(obj, dict):
            return None

        if "@graph" in obj and isinstance(obj["@graph"], list):
            for node in obj["@graph"]:
                product = self._product_from_json_ld_object(node, url, domain)
                if product is not None:
                    return product
            return None

        type_field = obj.get("@type")
        types = type_field if isinstance(type_field, list) else [type_field]
        if not any(isinstance(t, str) and t.lower() == "product" for t in types):
            return None

        name = obj.get("name")
        image = obj.get("image")
        if isinstance(image, list):
            image = image[0] if image else None
        elif isinstance(image, dict):
            image = image.get("url")

        offers = obj.get("offers")
        offer = None
        if isinstance(offers, list) and offers:
            offer = offers[0]
        elif isinstance(offers, dict):
            offer = offers

        price = None
        currency = None
        availability = None
        if offer:
            raw_price = offer.get("price") or offer.get("lowPrice")
            price = extract_numeric_price(raw_price)
            if price is not None and not is_plausible_amount(price):
                price = None
            currency = currency_resolver.resolve(
                json_ld_currency=offer.get("priceCurrency"),
                url=url,
            )
            raw_availability = offer.get("availability") or ""
            if raw_availability:
                availability = raw_availability.rsplit("/", 1)[-1]

        rating = None
        review_count = None
        agg = obj.get("aggregateRating")
        if isinstance(agg, dict):
            rating_value = agg.get("ratingValue")
            if rating_value is not None:
                try:
                    rating = round(min(float(rating_value), 5.0), 2)
                except (TypeError, ValueError):
                    rating = None
            count = agg.get("reviewCount") or agg.get("ratingCount")
            if count is not None:
                try:
                    review_count = int(float(count))
                except (TypeError, ValueError):
                    review_count = None

        variant_info = self._variant_info_from_json_ld(obj)

        if not name:
            return None

        return OfficialProduct(
            platform="Official Website",
            title=name,
            link=url,
            source_domain=domain,
            price=price,
            currency=currency,
            thumbnail=image,
            rating=rating,
            review_count=review_count,
            availability=availability,
            variant_info=variant_info,
            price_source="official_website",
            extraction_method="json_ld",
            confidence_score=0.9 if price is not None else 0.6,
        )

    def _variant_info_from_json_ld(self, obj: dict) -> str | None:
        variants = obj.get("hasVariant")
        if isinstance(variants, list) and variants:
            names = [v.get("name") for v in variants if isinstance(v, dict) and v.get("name")]
            if names:
                return ", ".join(names[:5])

        props = obj.get("additionalProperty")
        if isinstance(props, list) and props:
            parts = []
            for prop in props:
                if isinstance(prop, dict) and prop.get("name") and prop.get("value"):
                    parts.append(f"{prop['name']}: {prop['value']}")
            if parts:
                return ", ".join(parts[:5])

        return None

    def _from_opengraph(
        self, soup: BeautifulSoup, url: str, domain: str, brand_name: str
    ) -> OfficialProduct | None:
        title_tag = soup.find("meta", attrs={"property": "og:title"})
        if not title_tag or not title_tag.get("content"):
            return None

        image_tag = soup.find("meta", attrs={"property": "og:image"})
        price_tag = soup.find("meta", attrs={"property": "og:price:amount"}) or soup.find(
            "meta", attrs={"property": "product:price:amount"}
        )
        currency_tag = soup.find("meta", attrs={"property": "og:price:currency"}) or soup.find(
            "meta", attrs={"property": "product:price:currency"}
        )

        price = None
        if price_tag and price_tag.get("content"):
            price = extract_numeric_price(price_tag["content"])
            if price is not None and not is_plausible_amount(price):
                price = None

        currency = currency_resolver.resolve(
            opengraph_currency=currency_tag.get("content") if currency_tag else None,
            url=url,
        )

        return OfficialProduct(
            platform="Official Website",
            title=title_tag["content"],
            link=url,
            source_domain=domain,
            price=price,
            currency=currency,
            thumbnail=image_tag.get("content") if image_tag else None,
            price_source="official_website",
            extraction_method="opengraph",
            confidence_score=0.75 if price is not None else 0.5,
        )
