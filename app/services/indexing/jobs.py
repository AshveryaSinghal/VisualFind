"""
Persisted status tracking for indexing runs - batch runs (CSV upload,
partner API pull, rebuilds), which can be large enough that the caller
needs to submit-and-poll instead of waiting on an open HTTP request, and
also every live-search (Google Lens) background indexing run (see
app/services/indexing/runner.py::index_purchase_links_in_background) -
nobody polls those individually, but recording them here is what lets
index_dashboard_service.py's "average indexing time" reflect real
indexing volume instead of just the rare batch jobs.

Every function here takes its own `db: Session` and commits its own
change; this module is designed to be called from a background task with
a dedicated session (see routers/product_index.py), never sharing a
session with the request that kicked the job off.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database import IndexingJob
from app.services.indexing.types import IndexingResult, SourceType

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_job(
    db: Session,
    *,
    source_type: SourceType,
    source_label: str | None,
    total: int,
    index_version_id: int | None = None,
) -> IndexingJob:
    job = IndexingJob(
        source_type=source_type.value,
        source_label=source_label,
        status="queued",
        total_received=total,
        index_version_id=index_version_id,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def mark_running(db: Session, job_id: int) -> None:
    job = db.query(IndexingJob).filter(IndexingJob.id == job_id).first()
    if job is None:
        return
    job.status = "running"
    job.started_at = _utcnow()
    db.commit()


def mark_completed(db: Session, job_id: int, result: IndexingResult) -> None:
    job = db.query(IndexingJob).filter(IndexingJob.id == job_id).first()
    if job is None:
        return
    job.status = "completed"
    job.total_received = result.total_received
    job.invalid = result.invalid
    job.duplicates_removed = result.duplicates_removed
    job.created = result.created
    job.updated = result.updated
    job.embedded = result.embedded
    job.failed = result.failed
    if result.errors:
        job.error_message = "; ".join(result.errors[:10])
    job.completed_at = _utcnow()
    db.commit()


def mark_failed(db: Session, job_id: int, error: str) -> None:
    job = db.query(IndexingJob).filter(IndexingJob.id == job_id).first()
    if job is None:
        return
    job.status = "failed"
    job.error_message = error[:2000]
    job.completed_at = _utcnow()
    db.commit()
    logger.error("Indexing job %s failed: %s", job_id, error)


def get_job(db: Session, job_id: int) -> IndexingJob | None:
    return db.query(IndexingJob).filter(IndexingJob.id == job_id).first()


def list_jobs(db: Session, limit: int = 20) -> list[IndexingJob]:
    return db.query(IndexingJob).order_by(IndexingJob.created_at.desc()).limit(limit).all()
