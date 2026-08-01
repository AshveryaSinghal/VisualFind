"""
Index Rebuild: recomputes the Product Index's search-relevant state - each
catalog row's embedding, primarily - for every row already in
ProductIndexEntry, and stamps the result with a new IndexVersion (see
versioning.py).

This is deliberately a *separate* path from the day-to-day
IndexingPipeline (pipeline.py): the pipeline's job is turning newly
discovered products into catalog rows (normalize -> dedupe -> store ->
embed). Rebuild's job is refreshing rows that already exist - the tool you
reach for after swapping `settings.product_index_embedding_backend`, after
a normalization bug is fixed and old rows need re-cleaning, or just on a
schedule to guarantee the whole catalog reflects one consistent backend
instead of a patchwork of whichever backend was active when each row was
last touched. Nothing here creates or dedupes new products; upsert_product
already owns that.

Two ways to trigger this:
  - CLI: `python -m app.scripts.rebuild_index` (see that file) - for an
    operator running it directly, no HTTP server required.
  - API: POST /api/product-index/index/rebuild, which schedules
    run_rebuild_job() (indexing/runner.py) as a background task and
    returns immediately with a pollable IndexingJob, same pattern as CSV/
    API batch indexing.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.config import settings
from app.database import ProductIndexEntry
from app.services.indexing import versioning
from app.services.indexing.normalize import normalize_raw_product
from app.services.indexing.types import RawProduct
from app.services.product_index import service as product_index_service
from app.services.product_index.embedding_service import default_embedding_service

logger = logging.getLogger(__name__)

_DB_COMMIT_BATCH_SIZE = 200


@dataclass
class RebuildResult:
    """Summary of one rebuild run - mirrors IndexingResult's shape
    (indexing/types.py) closely enough to reuse the same dashboard/response
    conventions, but describes refreshing existing rows rather than
    ingesting new ones."""

    version_id: int | None = None
    version_number: int | None = None
    total_entries: int = 0
    renormalized: int = 0
    re_embedded: int = 0
    embedding_failed: int = 0
    errors: list[str] = field(default_factory=list)
    status: str = "building"

    def to_dict(self) -> dict:
        return {
            "version_id": self.version_id,
            "version_number": self.version_number,
            "total_entries": self.total_entries,
            "renormalized": self.renormalized,
            "re_embedded": self.re_embedded,
            "embedding_failed": self.embedding_failed,
            "status": self.status,
            "errors": self.errors[:20],
        }


def _renormalize_entry(entry: ProductIndexEntry) -> bool:
    """Re-runs stage-1 normalization (normalize.py) against an entry's
    already-stored fields, in place. Returns True if anything changed.
    This is what lets a rebuild also pick up normalization-logic fixes
    (a smarter brand guesser, a better title cleaner, ...) for products
    that were catalogued before the fix shipped, not just re-embed them."""
    raw = RawProduct(
        title=entry.title,
        brand=entry.brand,
        category=entry.category,
        image_url=entry.image_url,
        description=entry.description,
        price=entry.price,
        currency=entry.currency,
        rating=entry.rating,
        review_count=entry.review_count,
        source=entry.source,
        product_url=entry.product_url,
    )
    cleaned = normalize_raw_product(raw)
    if cleaned is None:
        return False

    changed = False
    for field_name in ("title", "brand", "category", "description", "currency"):
        new_value = getattr(cleaned, field_name)
        if new_value and new_value != getattr(entry, field_name):
            setattr(entry, field_name, new_value)
            changed = True
    return changed


def _re_embed_entries(
    entries: list[ProductIndexEntry], *, force: bool, workers: int, max_embeddings: int | None
) -> tuple[int, int]:
    """Returns (re_embedded, embedding_failed). When `force` is True, every
    entry with an image is recomputed regardless of
    EmbeddingService.needs_embedding (used for a genuine full rebuild,
    e.g. after swapping backends); when False, only entries that already
    need one are touched (a cheaper "catch up the stragglers" rebuild)."""
    backend = default_embedding_service.backend
    candidates = [
        entry
        for entry in entries
        if entry.image_url and (force or default_embedding_service.needs_embedding(entry))
    ]
    if max_embeddings is not None:
        candidates = candidates[:max_embeddings]
    if not candidates:
        return 0, 0

    def _compute(entry: ProductIndexEntry):
        image_bytes = default_embedding_service.download_image(entry.image_url)
        if image_bytes is None:
            return entry, None
        try:
            return entry, backend.embed(image_bytes)
        except Exception:
            logger.debug("Rebuild: embedding failed for entry id=%s", entry.id, exc_info=True)
            return entry, None

    re_embedded = 0
    failed = 0
    worker_count = max(1, min(workers, len(candidates)))
    with ThreadPoolExecutor(max_workers=worker_count) as pool:
        futures = [pool.submit(_compute, entry) for entry in candidates]
        for future in as_completed(futures):
            entry, vector = future.result()
            if vector is None:
                failed += 1
                continue
            product_index_service._apply_embedding(entry, vector, model_name=backend.name)
            re_embedded += 1

    return re_embedded, failed


def rebuild_index(
    db: Session,
    *,
    full_reembed: bool = True,
    renormalize: bool = True,
    max_embeddings: int | None = None,
    workers: int | None = None,
    label: str | None = None,
    triggered_by: str = "manual",
    version_id: int | None = None,
) -> RebuildResult:
    """Runs a full (or catch-up) rebuild over every row currently in the
    Product Index. Never raises for a problem with an individual entry -
    those are counted, same convention as IndexingPipeline.run() - but does
    raise (after recording the version as failed) if the whole run can't
    proceed, e.g. the Product Index is disabled.

    `full_reembed=True` recomputes every entry's embedding regardless of
    whether it's already current - the thing you want after swapping
    embedding backends. `full_reembed=False` only fills in entries that are
    missing one or are stamped with a stale backend - cheaper, for a
    routine "catch the catalog up" run.

    `version_id`, when given, reuses an already-`building` IndexVersion
    (created ahead of time by a caller that needs the id before the run
    starts - see routers/product_index.py's rebuild endpoint) instead of
    starting a new one, so a rebuild is described by exactly one version
    row, never two.
    """
    backend = default_embedding_service.backend
    total_entries = db.query(ProductIndexEntry).count()

    if version_id is not None:
        version = versioning.get_version(db, version_id)
        if version is None:
            raise ValueError(f"No IndexVersion with id={version_id}")
        version.embedding_backend = backend.name
        version.total_entries = total_entries
        db.commit()
        db.refresh(version)
    else:
        version = versioning.start_version(
            db,
            label=label,
            embedding_backend=backend.name,
            triggered_by=triggered_by,
            notes=f"full_reembed={full_reembed} renormalize={renormalize}",
            total_entries=total_entries,
        )
    result = RebuildResult(version_id=version.id, version_number=version.version_number, total_entries=total_entries)

    if not settings.enable_product_index:
        error = "Product Index is disabled (settings.enable_product_index=False)"
        result.errors.append(error)
        result.status = "failed"
        versioning.finish_version_failed(db, version.id, error)
        return result

    try:
        entries = db.query(ProductIndexEntry).all()

        if renormalize:
            renormalized = 0
            for i, entry in enumerate(entries, start=1):
                try:
                    if _renormalize_entry(entry):
                        renormalized += 1
                except Exception as exc:
                    result.errors.append(f"renormalize id={entry.id}: {exc}")
                if i % _DB_COMMIT_BATCH_SIZE == 0:
                    db.commit()
            db.commit()
            result.renormalized = renormalized

        if settings.product_index_embedding_enabled:
            cap = settings.indexing_batch_max_embeddings if max_embeddings is None else max_embeddings
            worker_count = settings.indexing_embedding_workers if workers is None else workers
            re_embedded, embedding_failed = _re_embed_entries(
                entries, force=full_reembed, workers=worker_count, max_embeddings=cap
            )
            result.re_embedded = re_embedded
            result.embedding_failed = embedding_failed
            db.commit()

        # Stamp every entry with this version, whether or not it needed
        # re-embedding this run - "reflects the active version" (see index
        # health monitoring) means "was covered by this rebuild pass", not
        # "its vector literally changed this time".
        for i, entry in enumerate(entries, start=1):
            entry.index_version = version.version_number
            if i % _DB_COMMIT_BATCH_SIZE == 0:
                db.commit()
        db.commit()

        versioning.finish_version_success(
            db,
            version.id,
            total_entries=total_entries,
            embedded_entries=result.re_embedded,
            failed_entries=result.embedding_failed,
        )
        result.status = "active"
    except Exception as exc:
        db.rollback()
        logger.exception("Index rebuild failed (version_number=%s)", version.version_number)
        versioning.finish_version_failed(db, version.id, str(exc))
        result.status = "failed"
        result.errors.append(str(exc))

    logger.info(
        "Index Rebuild | version=%s total=%d renormalized=%d re_embedded=%d embedding_failed=%d status=%s",
        result.version_number, result.total_entries, result.renormalized,
        result.re_embedded, result.embedding_failed, result.status,
    )
    return result
