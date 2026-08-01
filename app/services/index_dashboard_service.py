"""
Aggregation for the Index Statistics dashboard.

Pulls together three things that already exist as separate tables but have
never been summarized in one place:
  1. The Product Index catalog itself (app.database.ProductIndexEntry) -
     how many products, how many categories/brands, how far along
     embedding backfill is, and how fast the catalog is growing (new rows
     in the last 24h/7d, and a 7-day daily series).
  2. The Indexing Pipeline's job history (app.database.IndexingJob) - how
     many products have been received, how many of those were duplicates
     the pipeline collapsed away (see app/services/indexing/service dedupe
     step), and how long a run takes on average (started_at/completed_at,
     now stamped for *every* run including live-search background
     indexing - see app/services/indexing/runner.py).
  3. Search history (app.database.SearchLog) - how fast searches answer,
     how often the response came from cache, and how often the internal
     Product Index contributed supplemental "also in our catalog"
     recommendations alongside Google Lens's primary results (see
     app/services/search_service.py).

Deliberately read-only and side-effect free, same spirit as
app/services/analytics_service.py - just aggregation queries over data
that's already being written on the hot paths.
"""

from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import IndexingJob, ProductIndexEntry, SearchLog
from app.models import IndexStatsResponse

_TOP_N = 10
_GROWTH_WINDOW_DAYS = 7


def _top_n(counter: Counter, n: int = _TOP_N) -> list[dict]:
    return [{"name": name, "count": count} for name, count in counter.most_common(n) if name]


def _pct(numerator: int, denominator: int) -> float | None:
    if not denominator:
        return None
    return round((numerator / denominator) * 100, 1)


def _catalog_stats(db: Session) -> dict:
    total_products = db.query(ProductIndexEntry).count()
    products_with_embeddings = (
        db.query(ProductIndexEntry).filter(ProductIndexEntry.embedding_json.isnot(None)).count()
    )

    by_category = dict(
        db.query(ProductIndexEntry.category, func.count(ProductIndexEntry.id))
        .filter(ProductIndexEntry.category.isnot(None))
        .group_by(ProductIndexEntry.category)
        .all()
    )
    by_brand = dict(
        db.query(ProductIndexEntry.brand, func.count(ProductIndexEntry.id))
        .filter(ProductIndexEntry.brand.isnot(None))
        .group_by(ProductIndexEntry.brand)
        .all()
    )
    by_source = dict(
        db.query(ProductIndexEntry.source, func.count(ProductIndexEntry.id))
        .filter(ProductIndexEntry.source.isnot(None))
        .group_by(ProductIndexEntry.source)
        .all()
    )

    return {
        "total_products": total_products,
        "total_categories": len(by_category),
        "total_brands": len(by_brand),
        "by_category": by_category,
        "by_brand": by_brand,
        "by_source": by_source,
        "products_with_embeddings": products_with_embeddings,
        "embedding_progress_pct": _pct(products_with_embeddings, total_products) or 0.0,
    }


def _naive(dt: datetime) -> datetime:
    """Normalizes to a naive UTC datetime for comparison. `_utcnow()` (see
    app/database.py) writes tz-aware UTC timestamps, but SQLite - this
    app's default backend - strips tzinfo on round-trip, so rows read back
    naive; other backends (Postgres) may not. Comparing tz-aware and naive
    datetimes raises, so every timestamp is normalized to naive-UTC before
    any comparison, same convention app/services/analytics_service.py
    already uses for its own day-bucket math."""
    return dt.replace(tzinfo=None) if dt.tzinfo is not None else dt


def _growth_stats(db: Session) -> dict:
    """How fast the catalog is growing: new products in the last 24h/7d,
    plus a 7-day daily series for a trend chart - the "index growth"
    metric that total_products (a single snapshot, see _catalog_stats)
    can't show on its own."""
    now = _naive(datetime.utcnow())
    window_start = now - timedelta(days=_GROWTH_WINDOW_DAYS - 1)
    cutoff_24h = now - timedelta(hours=24)

    day_buckets: dict[str, int] = {
        (window_start + timedelta(days=offset)).strftime("%Y-%m-%d"): 0
        for offset in range(_GROWTH_WINDOW_DAYS)
    }

    rows = (
        db.query(ProductIndexEntry.created_at)
        .filter(ProductIndexEntry.created_at.isnot(None))
        .filter(ProductIndexEntry.created_at >= window_start)
        .all()
    )

    last_24h = 0
    last_7d = 0
    for (created_at,) in rows:
        ts = _naive(created_at)
        last_7d += 1
        if ts >= cutoff_24h:
            last_24h += 1
        day_key = ts.strftime("%Y-%m-%d")
        if day_key in day_buckets:
            day_buckets[day_key] += 1

    return {
        "index_growth_last_24h": last_24h,
        "index_growth_last_7d": last_7d,
        "index_growth_by_day": [{"date": day, "count": count} for day, count in day_buckets.items()],
    }


def _indexing_time_stats(db: Session) -> dict:
    """Average indexing time across every completed IndexingJob run - CSV/
    API/rebuild batches *and* live-search background runs (see
    app/services/indexing/runner.py::index_purchase_links_in_background,
    which now creates a job row too), so this reflects real indexing
    latency rather than only the rare batch imports."""
    rows = (
        db.query(IndexingJob.source_type, IndexingJob.started_at, IndexingJob.completed_at)
        .filter(IndexingJob.status == "completed")
        .filter(IndexingJob.started_at.isnot(None))
        .filter(IndexingJob.completed_at.isnot(None))
        .all()
    )

    durations_by_source: dict[str, list[float]] = {}
    all_durations: list[float] = []
    for source_type, started_at, completed_at in rows:
        delta_ms = (_naive(completed_at) - _naive(started_at)).total_seconds() * 1000
        if delta_ms < 0:
            continue
        all_durations.append(delta_ms)
        durations_by_source.setdefault(source_type or "unknown", []).append(delta_ms)

    return {
        "average_indexing_time_ms": round(sum(all_durations) / len(all_durations), 1) if all_durations else None,
        "indexing_runs_measured": len(all_durations),
        "average_indexing_time_by_source": {
            source: round(sum(vals) / len(vals), 1) for source, vals in durations_by_source.items()
        },
    }


def _duplicate_stats(db: Session) -> dict:
    row = db.query(
        func.count(IndexingJob.id),
        func.coalesce(func.sum(IndexingJob.total_received), 0),
        func.coalesce(func.sum(IndexingJob.duplicates_removed), 0),
        func.coalesce(func.sum(IndexingJob.created), 0),
        func.coalesce(func.sum(IndexingJob.updated), 0),
    ).first()
    total_jobs, total_received, total_duplicates, total_created, total_updated = row

    return {
        "total_indexing_jobs": total_jobs or 0,
        "total_products_received": total_received or 0,
        "total_duplicates_removed": total_duplicates or 0,
        "total_created": total_created or 0,
        "total_updated": total_updated or 0,
        "duplicate_rate_pct": _pct(total_duplicates or 0, total_received or 0),
    }


def _search_stats(db: Session) -> dict:
    logs = db.query(
        SearchLog.query_source,
        SearchLog.execution_time_ms,
        SearchLog.best_guess_label,
        SearchLog.product_query,
        SearchLog.detected_brand,
    ).all()

    total_searches = len(logs)
    if total_searches == 0:
        return {
            "total_searches": 0,
            "average_search_latency_ms": None,
            "cache_hit_searches": 0,
            "cache_hit_rate_pct": None,
            "internal_index_searches": 0,
            "internal_index_share_pct": None,
            "lens_fallback_searches": 0,
            "lens_fallback_share_pct": None,
            "top_searched_products": [],
            "top_searched_brands": [],
        }

    cache_hits = sum(1 for row in logs if row.query_source == "cache")
    # Google Lens is always the primary pipeline for every live (non-cache)
    # search now - see search_service.process_image_search. What varies is
    # only whether the internal Product Index also contributed a few
    # supplemental "also in our catalog" recommendations, appended after
    # Lens's own results (query_source gets a "+index_supplement" suffix
    # when it did - see search_service._supplement_with_internal_index).
    index_supplemented_hits = sum(
        1 for row in logs if (row.query_source or "").endswith("+index_supplement")
    )
    lens_only_hits = total_searches - cache_hits - index_supplemented_hits

    # Cache replays short-circuit the whole pipeline and are recorded with
    # execution_time_ms=0 (see search_service._build_response_from_cache) -
    # including them here would understate genuine pipeline latency, and
    # cache_hit_rate already surfaces how often that shortcut is taken.
    live_latencies = [row.execution_time_ms for row in logs if row.query_source != "cache" and row.execution_time_ms is not None]

    # Share of *live* searches (excludes cache replays).
    live_total = index_supplemented_hits + lens_only_hits

    product_counter = Counter(
        (row.best_guess_label or row.product_query or "").strip().lower()
        for row in logs
        if (row.best_guess_label or row.product_query)
    )
    brand_counter = Counter(row.detected_brand.strip().lower() for row in logs if row.detected_brand)

    return {
        "total_searches": total_searches,
        "average_search_latency_ms": round(sum(live_latencies) / len(live_latencies), 1) if live_latencies else None,
        "cache_hit_searches": cache_hits,
        "cache_hit_rate_pct": _pct(cache_hits, total_searches),
        # Field names kept for API/frontend compatibility, but the meaning
        # has shifted: "internal_index_searches" is now "Google Lens
        # searches the internal index also supplemented", not "answered by
        # the index alone" (that path no longer exists - see above).
        "internal_index_searches": index_supplemented_hits,
        "internal_index_share_pct": _pct(index_supplemented_hits, live_total),
        "lens_fallback_searches": lens_only_hits,
        "lens_fallback_share_pct": _pct(lens_only_hits, live_total),
        "top_searched_products": _top_n(product_counter),
        "top_searched_brands": _top_n(brand_counter),
    }


def get_index_dashboard_stats(db: Session) -> IndexStatsResponse:
    data: dict = {}
    data.update(_catalog_stats(db))
    data.update(_growth_stats(db))
    data.update(_duplicate_stats(db))
    data.update(_indexing_time_stats(db))
    data.update(_search_stats(db))
    return IndexStatsResponse(**data)
