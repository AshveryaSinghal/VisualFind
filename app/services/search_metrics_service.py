"""
Search Latency Metrics.

Deliberately a *read model* over the already-persisted SearchLog table
(app/database.py), not a new instrumentation point - every search path
(image search's internal-index/Lens/cache branches, text search, hybrid
search) already writes execution_time_ms on every SearchLog row it
creates. Computing percentiles here means zero changes to any existing
search code path - "search latency metrics" is additive, read-only
aggregation, same spirit as index_dashboard_service.py.

Cache-served responses are recorded with execution_time_ms=0 by design
(they short-circuit the whole pipeline - see search_service.py) and are
excluded from latency percentiles for the same reason
index_dashboard_service excludes them from average_search_latency_ms:
including a flood of zeros would understate genuine pipeline latency
without saying anything about it. They're still counted separately as
`cache_hits` so callers can see the cache's effect on overall traffic.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.database import SearchLog


def _percentile(sorted_values: list[int], pct: float) -> float | None:
    """Nearest-rank percentile over an already-sorted list. `pct` in
    [0, 100]. No dependency on numpy - this list is at most a few thousand
    ints, plain Python is plenty fast."""
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    rank = pct / 100 * (len(sorted_values) - 1)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return float(sorted_values[lower])
    weight = rank - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def get_search_latency_metrics(
    db: Session,
    *,
    window_minutes: int | None = None,
    limit: int = 5000,
) -> dict:
    """Latency percentiles + a breakdown by query_source (internal_index /
    google Lens fallback labels / cache / hybrid / text / ai_chat, ...).

    `window_minutes`, when given, restricts to SearchLog rows created in
    the last N minutes (for "how is search behaving right now"); omitted,
    it looks at the most recent `limit` searches regardless of age (for
    "what does typical latency look like").
    """
    query = db.query(SearchLog.query_source, SearchLog.execution_time_ms, SearchLog.created_at)
    if window_minutes is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        query = query.filter(SearchLog.created_at >= cutoff)
    rows = query.order_by(SearchLog.created_at.desc()).limit(limit).all()

    total_searches = len(rows)
    cache_hits = sum(1 for row in rows if (row.query_source or "").endswith("cache"))

    # Only "live" (non-cache) latencies represent real pipeline work - see
    # module docstring.
    live = sorted(
        row.execution_time_ms
        for row in rows
        if row.execution_time_ms is not None and not (row.query_source or "").endswith("cache")
    )

    by_source: dict[str, dict] = {}
    for row in rows:
        key = row.query_source or "unknown"
        by_source.setdefault(key, []).append(row.execution_time_ms or 0)

    source_breakdown = {}
    for source, latencies in by_source.items():
        latencies_sorted = sorted(latencies)
        source_breakdown[source] = {
            "count": len(latencies_sorted),
            "average_ms": round(sum(latencies_sorted) / len(latencies_sorted), 1) if latencies_sorted else None,
            "p95_ms": _percentile(latencies_sorted, 95),
        }

    return {
        "window_minutes": window_minutes,
        "sample_size": total_searches,
        "cache_hits": cache_hits,
        "live_searches": len(live),
        "average_latency_ms": round(sum(live) / len(live), 1) if live else None,
        "min_latency_ms": live[0] if live else None,
        "max_latency_ms": live[-1] if live else None,
        "p50_latency_ms": _percentile(live, 50),
        "p95_latency_ms": _percentile(live, 95),
        "p99_latency_ms": _percentile(live, 99),
        "by_query_source": source_breakdown,
    }
