"""
Stage 2 of the indexing pipeline: remove duplicates.

There are two dedup layers in the app, deliberately kept separate:

  1. This module - in-*batch* dedup, run before anything ever touches the
     database. A single Lens response, CSV upload, or API pull can easily
     contain the same physical product more than once (the same row twice
     in a supplier export, a product re-listed under an identical title).
     Collapsing those here means the DB layer below only ever sees one
     write per real product, instead of doing N redundant SELECT+UPDATEs
     for what was actually one item.
  2. app/services/product_index/service.py::upsert_product - cross-*time*
     dedup, keyed on the same normalized (title, brand) key
     (product_index_service.product_key), so a product discovered again
     in a *future* batch/search refreshes its existing row instead of
     creating a second one.

Both layers use the exact same key derivation (product_key) - "is this a
duplicate" means the same thing whether it's decided pre-DB (here) or at
upsert time. Deliberately *not* also matching on product_url: two listings
that happen to share a URL (a redirect, a shortened/canonical link, a
placeholder in test/seed data) aren't necessarily the same product, and a
title+brand match is already the catalog's single source of truth for
product identity everywhere else - a second, looser notion of "duplicate"
here would make the pipeline's behavior surprising.
"""

from __future__ import annotations

from app.services.indexing.types import RawProduct
from app.services.product_index.service import product_key


def _dedup_key(product: RawProduct) -> str:
    return product_key(product.title or "", product.brand, product.source)


def _richness(product: RawProduct) -> tuple:
    """Rough "how much usable data does this row carry" score, used to
    pick the best representative among duplicates rather than blindly
    keeping whichever came first. More non-empty fields and a real price
    both count in the product's favor."""
    fields = (
        product.image_url,
        product.description,
        product.rating,
        product.review_count,
        product.product_url,
        product.currency,
    )
    return (sum(1 for f in fields if f not in (None, "")), product.price is not None)


def dedupe_batch(products: list[RawProduct]) -> tuple[list[RawProduct], int]:
    """Collapses duplicates within a single batch of already-normalized
    RawProducts, keyed on the same normalized (title, brand) key the
    catalog itself uses (product_index_service.product_key). When
    duplicates are found, the most "complete" one (see _richness) is kept,
    so a sparse duplicate row never overwrites a richer one just because
    it happened to be processed first. Order of the surviving items
    follows their first occurrence in the input.

    Returns (deduped_products, number_removed).
    """
    if not products:
        return [], 0

    best_by_key: dict[str, RawProduct] = {}
    order: list[str] = []

    for product in products:
        key = _dedup_key(product)
        existing = best_by_key.get(key)

        if existing is None:
            best_by_key[key] = product
            order.append(key)
            continue

        # Duplicate: keep whichever of the two carries more usable data.
        best_by_key[key] = product if _richness(product) > _richness(existing) else existing

    deduped = [best_by_key[key] for key in order]
    removed = len(products) - len(deduped)
    return deduped, removed

