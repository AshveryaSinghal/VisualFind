"""
Index Health Monitoring.

Runs a small set of independent checks against the Product Index and
summarizes them into one overall status (healthy / degraded / unhealthy),
the same "roll several signals into one number" idea the Ranking Engine
uses for search results (app/services/ranking/engine.py), applied here to
the index's own operational state instead of a single search's results.

Each check is a pure function of already-existing data (catalog table,
job history, version history, search-latency read-model) - this module
adds no new instrumentation, only aggregation - and produces one
HealthCheckItem: a status, a short message, and the numbers that produced
it (so a human reading the response can see *why*, not just *that*).

`run_health_check(persist=True)` also writes an IndexHealthSnapshot row so
health can be trended over time (GET /health/history) instead of only
ever reflecting the instant it was called - same "call it, it catches up"
spirit as backfill_embeddings, not a background schedule in this phase.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import settings
from app.database import IndexHealthSnapshot, IndexingJob, ProductIndexEntry
from app.services.indexing import versioning
from app.services.product_index.embedding_service import default_embedding_service
from app.services.search_metrics_service import get_search_latency_metrics

# Order matters for computing the overall status: worse status always wins.
_STATUS_RANK = {"healthy": 0, "degraded": 1, "unhealthy": 2}


def _worse(a: str, b: str) -> str:
    return a if _STATUS_RANK[a] >= _STATUS_RANK[b] else b


def _check_embedding_coverage(db: Session) -> dict:
    total = db.query(ProductIndexEntry).count()
    embedded = db.query(ProductIndexEntry).filter(ProductIndexEntry.embedding_json.isnot(None)).count()
    pct = round((embedded / total) * 100, 1) if total else 100.0

    if total == 0:
        status = "healthy"
        message = "Product Index is empty - nothing to embed yet."
    elif pct >= 90:
        status = "healthy"
        message = f"{pct}% of products have an embedding."
    elif pct >= 70:
        status = "degraded"
        message = f"Only {pct}% of products have an embedding. Consider running backfill-embeddings."
    else:
        status = "unhealthy"
        message = f"Only {pct}% of products have an embedding. Visual search coverage is significantly degraded."

    return {
        "name": "embedding_coverage",
        "status": status,
        "message": message,
        "details": {"total_products": total, "embedded_products": embedded, "coverage_pct": pct},
    }


def _check_stale_embeddings(db: Session) -> dict:
    """Entries whose stored embedding doesn't come from the *currently
    configured* backend - stale after a backend swap, until a rebuild
    catches them up."""
    total = db.query(ProductIndexEntry).count()
    current_backend = default_embedding_service.backend.name
    stale = (
        db.query(ProductIndexEntry)
        .filter(ProductIndexEntry.embedding_json.isnot(None))
        .filter(ProductIndexEntry.embedding_model != current_backend)
        .count()
    )
    pct = round((stale / total) * 100, 1) if total else 0.0

    if stale == 0:
        status, message = "healthy", "All embedded products use the currently configured backend."
    elif pct < 10:
        status, message = "degraded", f"{stale} product(s) ({pct}%) have a stale embedding backend."
    else:
        status = "unhealthy"
        message = f"{stale} product(s) ({pct}%) have a stale embedding backend. Run a full index rebuild."

    return {
        "name": "stale_embeddings",
        "status": status,
        "message": message,
        "details": {"stale_count": stale, "current_backend": current_backend, "stale_pct": pct},
    }


def _check_active_version(db: Session) -> dict:
    active = versioning.get_active_version(db)
    if active is None:
        return {
            "name": "index_version",
            "status": "degraded",
            "message": "No index version has ever been activated. Run an initial index rebuild.",
            "details": {"active_version": None},
        }

    age_days = None
    if active.activated_at is not None:
        activated_at = active.activated_at
        if activated_at.tzinfo is None:
            activated_at = activated_at.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - activated_at).days

    if age_days is not None and age_days > 30:
        status = "degraded"
        message = f"Active index version #{active.version_number} is {age_days} days old. Consider rebuilding."
    else:
        status = "healthy"
        message = f"Active index version #{active.version_number}."

    return {
        "name": "index_version",
        "status": status,
        "message": message,
        "details": {
            "active_version": active.version_number,
            "activated_at": active.activated_at.isoformat() if active.activated_at else None,
            "age_days": age_days,
        },
    }


def _check_recent_job_failures(db: Session, sample_size: int = 20) -> dict:
    recent_jobs = (
        db.query(IndexingJob.status)
        .order_by(IndexingJob.created_at.desc())
        .limit(sample_size)
        .all()
    )
    total = len(recent_jobs)
    failed = sum(1 for (status,) in recent_jobs if status == "failed")
    pct = round((failed / total) * 100, 1) if total else 0.0

    if total == 0:
        status, message = "healthy", "No indexing jobs have run yet."
    elif pct == 0:
        status, message = "healthy", f"0 of the last {total} indexing jobs failed."
    elif pct < 25:
        status, message = "degraded", f"{failed} of the last {total} indexing jobs failed ({pct}%)."
    else:
        status = "unhealthy"
        message = f"{failed} of the last {total} indexing jobs failed ({pct}%). Check job error messages."

    return {
        "name": "recent_job_failures",
        "status": status,
        "message": message,
        "details": {"sampled_jobs": total, "failed_jobs": failed, "failure_rate_pct": pct},
    }


def _check_search_latency(db: Session) -> dict:
    metrics = get_search_latency_metrics(db, window_minutes=60, limit=2000)
    p95 = metrics["p95_latency_ms"]

    if p95 is None:
        status, message = "healthy", "No live searches in the last 60 minutes."
    elif p95 <= 2000:
        status, message = "healthy", f"p95 search latency is {p95:.0f}ms over the last hour."
    elif p95 <= 5000:
        status, message = "degraded", f"p95 search latency is {p95:.0f}ms over the last hour (elevated)."
    else:
        status = "unhealthy"
        message = f"p95 search latency is {p95:.0f}ms over the last hour (very slow)."

    return {
        "name": "search_latency",
        "status": status,
        "message": message,
        "details": {"window_minutes": 60, "p95_latency_ms": p95, "sample_size": metrics["live_searches"]},
    }


def _check_product_index_enabled() -> dict:
    if settings.enable_product_index:
        return {"name": "product_index_enabled", "status": "healthy", "message": "Product Index is enabled.", "details": {}}
    return {
        "name": "product_index_enabled",
        "status": "unhealthy",
        "message": "Product Index is disabled (settings.enable_product_index=False). Indexing and search are no-ops.",
        "details": {},
    }


def run_health_check(db: Session, *, persist: bool = True) -> dict:
    checks = [
        _check_product_index_enabled(),
        _check_embedding_coverage(db),
        _check_stale_embeddings(db),
        _check_active_version(db),
        _check_recent_job_failures(db),
        _check_search_latency(db),
    ]

    overall_status = "healthy"
    for check in checks:
        overall_status = _worse(overall_status, check["status"])
    issue_count = sum(1 for c in checks if c["status"] != "healthy")

    result = {
        "status": overall_status,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "issue_count": issue_count,
        "checks": checks,
    }

    if persist:
        snapshot = IndexHealthSnapshot(
            status=overall_status,
            checks_json=json.dumps(checks),
            issue_count=issue_count,
        )
        db.add(snapshot)
        db.commit()

    return result


def list_health_history(db: Session, limit: int = 20) -> list[dict]:
    rows = (
        db.query(IndexHealthSnapshot)
        .order_by(IndexHealthSnapshot.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": row.id,
            "status": row.status,
            "issue_count": row.issue_count,
            "checks": json.loads(row.checks_json),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
