"""
Background-task entry points for the indexing pipeline.

Every function here is meant to be handed to FastAPI's `BackgroundTasks`
(directly, or via `functools.partial`) rather than awaited/called inline -
that's what makes indexing "asynchronous where appropriate": the HTTP
response (a completed search, or a 202 for a batch job) goes back to the
caller immediately, and the actual normalize/dedupe/store/embed work
happens after, on its own database session.

A background task must never share a `Session` with the request that
scheduled it - that session is closed by the `get_db` dependency's
teardown as soon as the response is sent, regardless of whether a
background task is still using it. Every function below opens its own
session via `SessionLocal()` and closes it when done.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.database import SessionLocal
from app.models import PurchaseLink
from app.services.indexing import jobs, sources
from app.services.indexing.pipeline import default_pipeline
from app.services.indexing.rebuild import rebuild_index
from app.services.indexing.types import RawProduct, SourceType

logger = logging.getLogger(__name__)


def index_purchase_links_in_background(purchase_links: list[PurchaseLink]) -> None:
    """Scheduled after a Google Lens-backed search response has already
    been sent (see app/services/search_service.py) - the caller never
    waits on this. Errors are logged, never raised (there's no request
    left to raise them to).

    Also creates a (source_label="live_search") IndexingJob row, same as
    a batch/API run - not because anyone polls it (a per-search run is far
    too fast/frequent for that), but because it's the *majority* of real
    indexing volume. Without a job row here, "average indexing time" (see
    app/services/index_dashboard_service.py) would only ever reflect the
    rare CSV/API/rebuild runs and badly misrepresent typical indexing
    latency.
    """
    if not purchase_links:
        return
    db = SessionLocal()
    job_id: int | None = None
    try:
        job = jobs.create_job(
            db,
            source_type=SourceType.GOOGLE_LENS,
            source_label="live_search",
            total=len(purchase_links),
        )
        job_id = job.id
        jobs.mark_running(db, job_id)

        raw_products = sources.from_purchase_links(purchase_links)
        result = default_pipeline.run(db, raw_products, source_type=SourceType.GOOGLE_LENS)
        jobs.mark_completed(db, job_id, result)
    except Exception as exc:
        logger.exception("Background Lens indexing failed (non-fatal, search result was unaffected)")
        if job_id is not None:
            jobs.mark_failed(db, job_id, str(exc))
    finally:
        db.close()


def run_batch_job(job_id: int, raw_products: list[RawProduct], source_type: SourceType) -> None:
    """Runs a caller-supplied batch (already-parsed CSV rows, or a JSON
    batch request body) through the pipeline, updating the IndexingJob
    row throughout so GET /api/product-index/index/jobs/{id} reflects
    live progress."""
    db = SessionLocal()
    try:
        jobs.mark_running(db, job_id)
        result = default_pipeline.run(db, raw_products, source_type=source_type)
        jobs.mark_completed(db, job_id, result)
    except Exception as exc:
        logger.exception("Batch indexing job %s failed", job_id)
        jobs.mark_failed(db, job_id, str(exc))
    finally:
        db.close()


def run_rebuild_job(
    job_id: int,
    *,
    version_id: int,
    full_reembed: bool = True,
    renormalize: bool = True,
    max_embeddings: int | None = None,
    label: str | None = None,
) -> None:
    """Runs a full Product Index rebuild (app/services/indexing/rebuild.py)
    in the background, updating both the IndexingJob row (for
    GET /index/jobs/{id}) and the IndexVersion row (for
    GET /index/versions/{id}) throughout. `version_id` is the version the
    caller already created and linked to this job (see
    routers/product_index.py) before scheduling this task, so pollers can
    find the version even while the job is still queued/running, and the
    rebuild reuses that single version row instead of creating a second
    one.
    """
    db = SessionLocal()
    try:
        jobs.mark_running(db, job_id)
        rebuild_result = rebuild_index(
            db,
            full_reembed=full_reembed,
            renormalize=renormalize,
            max_embeddings=max_embeddings,
            label=label,
            triggered_by="api",
            version_id=version_id,
        )
        if rebuild_result.status == "failed":
            jobs.mark_failed(db, job_id, "; ".join(rebuild_result.errors) or "Rebuild failed")
        else:
            job = jobs.get_job(db, job_id)
            if job is not None:
                job.status = "completed"
                job.total_received = rebuild_result.total_entries
                job.updated = rebuild_result.renormalized
                job.embedded = rebuild_result.re_embedded
                job.failed = rebuild_result.embedding_failed
                if rebuild_result.errors:
                    job.error_message = "; ".join(rebuild_result.errors[:10])
                job.completed_at = datetime.now(timezone.utc)
                db.commit()
    except Exception as exc:
        logger.exception("Rebuild job %s failed", job_id)
        jobs.mark_failed(db, job_id, str(exc))
    finally:
        db.close()


def run_api_pull_job(job_id: int, api_url: str, source_label: str | None) -> None:
    """Fetches product records from a partner/supplier API URL, then runs
    them through the pipeline - the "future batch indexing from ... APIs"
    hook. Fetch failures (bad URL, non-JSON response, unrecognized shape)
    fail the job rather than crashing the process, same as any other
    per-job failure."""
    db = SessionLocal()
    try:
        jobs.mark_running(db, job_id)
        records = sources.fetch_json_records_from_api(api_url)
        raw_products = sources.from_json_records(records, default_source=source_label)
        result = default_pipeline.run(db, raw_products, source_type=SourceType.API)
        jobs.mark_completed(db, job_id, result)
    except Exception as exc:
        logger.exception("API-pull indexing job %s failed", job_id)
        jobs.mark_failed(db, job_id, str(exc))
    finally:
        db.close()
