"""
Versioned Indexes: bookkeeping for IndexVersion rows (see
app/database.py::IndexVersion for what a "version" means in this app - a
generation of full-rebuild state, not a duplicated copy of the catalog).

State machine, enforced by this module alone (nothing else should write
`status`/`activated_at` on an IndexVersion):

    building --(finish, success)--> active
    building --(finish, error)----> failed

Activating a version atomically archives whichever version was previously
active, so `status == "active"` is unique across the table at all times
(enforced here, not by a DB constraint, since SQLite's ALTER TABLE support
makes a partial-unique-index migration more trouble than it's worth for a
single-writer invariant like this one).

Every function takes its own `db: Session` and commits its own change,
same convention as app/services/indexing/jobs.py, since this is called
both from request-handling code and from background tasks with their own
session.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database import IndexVersion

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _next_version_number(db: Session) -> int:
    last = db.query(IndexVersion).order_by(IndexVersion.version_number.desc()).first()
    return (last.version_number + 1) if last else 1


def start_version(
    db: Session,
    *,
    label: str | None = None,
    embedding_backend: str | None = None,
    triggered_by: str = "manual",
    notes: str | None = None,
    total_entries: int = 0,
) -> IndexVersion:
    """Creates a new version in `building` status. Call this before doing
    any rebuild work, then finish_version_success()/finish_version_failed()
    once the rebuild completes - mirrors indexing/jobs.py's
    create_job -> mark_completed/mark_failed shape."""
    version = IndexVersion(
        version_number=_next_version_number(db),
        label=label,
        status="building",
        embedding_backend=embedding_backend,
        triggered_by=triggered_by,
        notes=notes,
        total_entries=total_entries,
    )
    db.add(version)
    db.commit()
    db.refresh(version)
    return version


def finish_version_success(
    db: Session,
    version_id: int,
    *,
    total_entries: int,
    embedded_entries: int,
    failed_entries: int,
) -> IndexVersion | None:
    """Marks a build as complete and activates it, archiving whatever
    version was active before. This is the only place a version's status
    ever becomes "active"."""
    version = get_version(db, version_id)
    if version is None:
        return None

    previous_active = (
        db.query(IndexVersion)
        .filter(IndexVersion.status == "active", IndexVersion.id != version_id)
        .all()
    )
    for old in previous_active:
        old.status = "archived"

    version.status = "active"
    version.total_entries = total_entries
    version.embedded_entries = embedded_entries
    version.failed_entries = failed_entries
    version.activated_at = _utcnow()
    version.completed_at = _utcnow()
    db.commit()
    db.refresh(version)
    logger.info(
        "Index Version %d activated | total=%d embedded=%d failed=%d",
        version.version_number, total_entries, embedded_entries, failed_entries,
    )
    return version


def finish_version_failed(db: Session, version_id: int, error: str) -> IndexVersion | None:
    version = get_version(db, version_id)
    if version is None:
        return None
    version.status = "failed"
    version.error_message = error[:2000]
    version.completed_at = _utcnow()
    db.commit()
    db.refresh(version)
    logger.error("Index Version %d failed: %s", version.version_number, error)
    return version


def get_version(db: Session, version_id: int) -> IndexVersion | None:
    return db.query(IndexVersion).filter(IndexVersion.id == version_id).first()


def get_active_version(db: Session) -> IndexVersion | None:
    return db.query(IndexVersion).filter(IndexVersion.status == "active").first()


def list_versions(db: Session, limit: int = 20) -> list[IndexVersion]:
    return db.query(IndexVersion).order_by(IndexVersion.version_number.desc()).limit(limit).all()
