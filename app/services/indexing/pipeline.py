"""
The Indexing Pipeline.

Whenever new products are discovered - from a completed Google Lens
search, a CSV upload, or a partner API pull - they should go through the
exact same five stages before landing in VisualFind's internal Product
Index:

  1. Normalize metadata   (normalize.normalize_batch)
  2. Remove duplicates    (dedup.dedupe_batch - collapses repeats *within*
                            this batch before anything touches the DB)
  3. Store products       (product_index_service.upsert_product - this is
                            also where cross-batch/cross-time duplicates
                            are caught, keyed on the same normalized
                            (title, brand) key used by stage 2)
  4. Generate embeddings  (default_embedding_service, parallelized across
                            a thread pool - see _embed_entries below)
  5. Update indexes       (stamping the computed vector back onto the
                            already-stored row - the embedding *is* the
                            index find_similar()/search_by_image() query
                            against, so "update indexes" and "store the
                            embedding" are the same commit)

Steps 4 and 5 run after step 3 (rather than before, as the numbered list
above might suggest) because whether a product even *needs* a fresh
embedding depends on whether it already has a current one from the active
backend (EmbeddingService.needs_embedding) - that can only be known once
the row exists. Conceptually this is still "generate embeddings, then
store, then index"; mechanically, storing first is what lets step 4 skip
products that don't actually need re-embedding.

This module is the only thing that should call
product_index_service.upsert_product() for a batch of newly-discovered
products - callers (search_service.py for Lens results, the CSV/API
routes for batch imports) should go through IndexingPipeline.run(), not
call upsert_product()/embed_product() directly, so every entry point gets
the same normalize -> dedupe -> store -> embed -> index behavior.
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from sqlalchemy.orm import Session

from app.config import settings
from app.database import ProductIndexEntry
from app.services.indexing.dedup import dedupe_batch
from app.services.indexing.normalize import normalize_batch
from app.services.indexing.types import IndexingResult, RawProduct, SourceType
from app.services.product_index import service as product_index_service
from app.services.product_index.embedding_service import default_embedding_service

logger = logging.getLogger(__name__)


def _embed_entries(entries: list[ProductIndexEntry], *, max_new_embeddings: int, workers: int) -> int:
    """Stage 4+5: computes embeddings for whichever `entries` still need
    one (see EmbeddingService.needs_embedding), up to `max_new_embeddings`,
    using a thread pool since each embedding is an independent, blocking
    network image download + backend.embed() call - this is the
    "asynchronous where appropriate" part of the pipeline. The DB itself is
    never touched from a worker thread: workers only download bytes and
    compute a vector; every mutation of an `entry` and every commit happens
    back on the calling thread.

    Returns how many entries got a *new* embedding.
    """
    backend = default_embedding_service.backend
    candidates = [
        entry
        for entry in entries
        if entry.image_url and default_embedding_service.needs_embedding(entry)
    ][:max_new_embeddings]

    if not candidates:
        return 0

    def _compute(entry: ProductIndexEntry):
        image_bytes = default_embedding_service.download_image(entry.image_url)
        if image_bytes is None:
            return entry, None
        try:
            vector = backend.embed(image_bytes)
        except Exception:
            logger.debug("Embedding computation failed for entry id=%s", entry.id, exc_info=True)
            vector = None
        return entry, vector

    embedded = 0
    worker_count = max(1, min(workers, len(candidates)))
    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        futures = [pool.submit(_compute, entry) for entry in candidates]
        for future in as_completed(futures):
            entry, vector = future.result()
            if vector is None:
                continue
            product_index_service._apply_embedding(entry, vector, model_name=backend.name)
            embedded += 1

    return embedded


class IndexingPipeline:
    """Stateless orchestrator - safe to share a single instance
    (`default_pipeline` below) across requests/threads since it holds no
    per-run state itself; everything it needs is passed into `run()`."""

    def run(
        self,
        db: Session,
        raw_products: list[RawProduct],
        *,
        source_type: SourceType,
        attempt_embeddings: bool = True,
        max_new_embeddings: int | None = None,
        embedding_workers: int | None = None,
    ) -> IndexingResult:
        """Runs every newly-discovered product in `raw_products` through
        the full pipeline and returns a summary. Never raises for a
        problem with an individual product (a bad row, a failed download,
        ...) - those are counted in the result instead - so one malformed
        item in a large batch never aborts the rest of the run.
        """
        run_start = time.perf_counter()
        result = IndexingResult(source_type=source_type, total_received=len(raw_products))
        if not raw_products:
            return result

        if not settings.enable_product_index:
            result.errors.append("Product Index is disabled (settings.enable_product_index=False)")
            return result

        # Stage 1: normalize.
        normalized, invalid = normalize_batch(raw_products)
        result.invalid = invalid

        # Stage 2: remove duplicates (within this batch).
        deduped, duplicates_removed = dedupe_batch(normalized)
        result.duplicates_removed = duplicates_removed

        # Stage 3: store (also catches cross-batch/cross-time duplicates
        # via the same normalized key, refreshing the existing row instead
        # of creating a second one).
        stored_entries: list[ProductIndexEntry] = []
        for product in deduped:
            try:
                existed_before = (
                    db.query(ProductIndexEntry.id)
                    .filter(ProductIndexEntry.product_key == product_index_service.product_key(
                        product.title or "", product.brand, product.source
                    ))
                    .first()
                    is not None
                )
                entry = product_index_service.upsert_product(
                    db,
                    title=product.title,
                    brand=product.brand,
                    category=product.category,
                    image_url=product.image_url,
                    description=product.description,
                    price=product.price if isinstance(product.price, (int, float)) else None,
                    currency=product.currency,
                    rating=product.rating,
                    review_count=product.review_count,
                    source=product.source,
                    product_url=product.product_url,
                    attempt_embedding=False,
                )
            except Exception as exc:
                result.failed += 1
                result.errors.append(f"{product.title!r}: {exc}")
                continue

            if entry is None:
                result.failed += 1
                result.errors.append(f"{product.title!r}: upsert returned no entry")
                continue

            stored_entries.append(entry)
            if existed_before:
                result.updated += 1
            else:
                result.created += 1

        # Stages 4 & 5: generate embeddings, update indexes.
        if attempt_embeddings and settings.product_index_embedding_enabled:
            cap = (
                settings.indexing_batch_max_embeddings
                if max_new_embeddings is None
                else max_new_embeddings
            )
            workers = settings.indexing_embedding_workers if embedding_workers is None else embedding_workers
            try:
                result.embedded = _embed_entries(stored_entries, max_new_embeddings=cap, workers=workers)
                if stored_entries:
                    db.commit()
            except Exception:
                logger.exception("Embedding stage failed for indexing run (source=%s)", source_type.value)
                db.rollback()

        result.entries = stored_entries
        result.duration_ms = int((time.perf_counter() - run_start) * 1000)

        logger.info(
            "Indexing Pipeline | source=%s received=%d invalid=%d duplicates=%d created=%d updated=%d "
            "embedded=%d failed=%d duration_ms=%d",
            source_type.value, result.total_received, result.invalid, result.duplicates_removed,
            result.created, result.updated, result.embedded, result.failed, result.duration_ms,
        )
        return result


default_pipeline = IndexingPipeline()
