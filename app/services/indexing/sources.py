"""
Source adapters: turn whatever shape a discovery channel hands us into the
one common RawProduct shape the pipeline understands (see types.py).

This is the intended extension point for "future batch indexing from CSVs
or APIs" - adding a new source is adding one small function here (and,
for a genuinely new *shape* of input, a column-alias map below), never a
change to normalize/dedup/pipeline.
"""

from __future__ import annotations

import csv
import io
import logging
from typing import Iterable

import requests

from app.models import PurchaseLink
from app.services.indexing.types import RawProduct, SourceType
from app.services.price_utils import extract_numeric_price

logger = logging.getLogger(__name__)

_REQUEST_HEADERS = {"User-Agent": "VisualFindIndexingPipeline/1.0"}
_DEFAULT_API_TIMEOUT_SECONDS = 10.0

# Column-name aliases tolerated for CSV/API records, since real-world
# supplier exports rarely use VisualFind's exact field names. First match
# wins; unmatched columns are ignored (kept in `raw` for debugging).
_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "title": ("title", "name", "product_name", "product_title"),
    "brand": ("brand", "manufacturer", "make"),
    "category": ("category", "product_category", "type"),
    "image_url": ("image_url", "image", "thumbnail", "img", "photo_url"),
    "description": ("description", "desc", "details", "summary"),
    "price": ("price", "cost", "amount", "sale_price", "mrp"),
    "currency": ("currency", "currency_code"),
    "rating": ("rating", "avg_rating", "star_rating"),
    "review_count": ("review_count", "reviews", "num_reviews", "review_total"),
    "source": ("source", "platform", "merchant", "vendor", "retailer"),
    "product_url": ("product_url", "url", "link", "product_link"),
    "external_id": ("external_id", "id", "sku", "product_id", "item_id"),
}


def from_purchase_links(links: Iterable[PurchaseLink]) -> list[RawProduct]:
    """Google Lens / Google Shopping results, already normalized into
    PurchaseLink by the search pipeline (see search_service.py). This is
    the "whenever new products are discovered from Google Lens" entry
    point."""
    products: list[RawProduct] = []
    for link in links:
        products.append(
            RawProduct(
                title=link.title,
                brand=link.brand,
                image_url=link.thumbnail,
                price=extract_numeric_price(link.price),
                currency=link.currency,
                rating=link.rating,
                review_count=link.review_count,
                source=link.platform,
                product_url=link.link,
                raw={"platform": link.platform, "extraction_method": link.extraction_method},
            )
        )
    return products


def _normalize_header(key: str) -> str:
    """"Product Name", "product-name", " Product_Name " -> "product_name",
    so supplier headers only need to match an alias loosely (case,
    surrounding whitespace, spaces/dashes vs underscores), not exactly."""
    return "_".join(key.strip().lower().replace("-", " ").split())


def _lookup(row: dict, aliases: tuple[str, ...]):
    normalized_row = {_normalize_header(k): v for k, v in row.items() if k}
    for key in aliases:
        value = normalized_row.get(key)
        if value not in (None, ""):
            return value
    return None


def _row_to_raw_product(row: dict, *, default_source: str | None = None) -> RawProduct:
    mapped = {field: _lookup(row, aliases) for field, aliases in _FIELD_ALIASES.items()}
    return RawProduct(
        title=mapped["title"],
        brand=mapped["brand"],
        category=mapped["category"],
        image_url=mapped["image_url"],
        description=mapped["description"],
        price=mapped["price"],
        currency=mapped["currency"],
        rating=mapped["rating"],
        review_count=mapped["review_count"],
        source=mapped["source"] or default_source,
        product_url=mapped["product_url"],
        external_id=str(mapped["external_id"]) if mapped["external_id"] is not None else None,
        raw=row,
    )


def from_csv_bytes(content: bytes, *, default_source: str | None = None) -> list[RawProduct]:
    """Parses an uploaded CSV file's raw bytes into RawProducts. Tolerates
    a BOM (common from Excel exports) and any of the column-name aliases
    in _FIELD_ALIASES; unrecognized columns are ignored rather than
    raising, so a supplier's extra columns never break the import."""
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    rows = [row for row in reader if any((v or "").strip() for v in row.values())]
    return [_row_to_raw_product(row, default_source=default_source) for row in rows]


def from_json_records(records: Iterable[dict], *, default_source: str | None = None) -> list[RawProduct]:
    """Parses a list of plain dicts (a JSON API response body, a batch
    POST request body, ...) into RawProducts using the same column-alias
    map as CSV import, so the same file/shape works from either an upload
    or a live API response."""
    return [_row_to_raw_product(dict(record), default_source=default_source) for record in records]


def fetch_json_records_from_api(
    url: str, *, headers: dict | None = None, timeout: float | None = None
) -> list[dict]:
    """Pulls a JSON array of product records from a partner/supplier API.
    Accepts either a bare JSON array, or an object with the array under a
    common key (`items`/`products`/`results`/`data`) - the shape most
    product-feed APIs actually use. Raises on network/parse failure;
    callers (see routers/product_index.py) are expected to surface that as
    a failed indexing job rather than silently swallowing it, since a
    misconfigured feed URL should be visible, not just logged.
    """
    request_headers = {**_REQUEST_HEADERS, **(headers or {})}
    response = requests.get(
        url, headers=request_headers, timeout=timeout or _DEFAULT_API_TIMEOUT_SECONDS
    )
    response.raise_for_status()
    payload = response.json()

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "products", "results", "data"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    raise ValueError(f"Could not find a list of product records in API response from {url!r}")


SOURCE_TYPE_LABELS = {
    SourceType.GOOGLE_LENS: "Google Lens",
    SourceType.CSV: "CSV Upload",
    SourceType.API: "Partner API",
    SourceType.MANUAL: "Manual",
    SourceType.REBUILD: "Full Index Rebuild",
}
