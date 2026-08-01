"""
Covers two things added on top of the existing indexing/dashboard code:

1. A regression proof that a product indexed through the pipeline is
   searchable via the internal index on the very next call - no separate
   "reindex"/"rebuild" step required (see vector_index.py's
   reconcile-on-every-search design).
2. The two dashboard metrics that didn't already exist: average indexing
   time (app/services/index_dashboard_service.py::_indexing_time_stats,
   now fed by every completed IndexingJob row including live-search
   background runs - see runner.py) and index growth
   (::_growth_stats).
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.services.indexing.runner as runner
from app.database import Base, IndexingJob, ProductIndexEntry
from app.models import PurchaseLink
from app.services import index_dashboard_service as dash
from app.services.indexing.pipeline import IndexingPipeline
from app.services.indexing.types import RawProduct, SourceType
from app.services.product_index import service as index_service
from app.services.product_index.embedding_backends.base import EmbeddingBackend


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


class _FixedVectorBackend(EmbeddingBackend):
    name = "fixed-vector-backend"
    dimension = 3

    def __init__(self, vector=None):
        self.vector = vector if vector is not None else [1.0, 0.0, 0.0]

    def embed(self, image_bytes: bytes) -> list[float]:
        return self.vector


def _use_backend(monkeypatch, backend):
    """Same fake-backend convention as test_product_index_service.py, plus
    a network-free download_image so pipeline._embed_entries (which
    downloads before embedding) never makes a real HTTP call."""
    monkeypatch.setattr(index_service.default_embedding_service, "_backend", backend)
    monkeypatch.setattr(
        index_service.default_embedding_service, "download_image", lambda url: b"fake-image-bytes"
    )
    return backend


def _link(title="Sony WH-1000XM5", brand="Sony", thumbnail=None):
    return PurchaseLink(
        platform="Amazon",
        title=title,
        brand=brand,
        price="24999",
        currency="INR",
        link="https://example.com/product",
        source_domain="example.com",
        thumbnail=thumbnail,
        rating=4.5,
        review_count=120,
    )


# --- Item 7: immediate searchability ---------------------------------------

def test_product_indexed_via_pipeline_is_immediately_searchable(monkeypatch):
    db = _session()
    _use_backend(monkeypatch, _FixedVectorBackend([1.0, 0.0, 0.0]))

    pipeline = IndexingPipeline()
    raw = [
        RawProduct(
            title="Sony WH-1000XM5", brand="Sony", image_url="https://example.com/a.jpg", source="Amazon"
        )
    ]
    result = pipeline.run(db, raw, source_type=SourceType.GOOGLE_LENS)
    assert result.embedded == 1

    entry = db.query(ProductIndexEntry).filter(ProductIndexEntry.title == "Sony WH-1000XM5").first()
    assert entry.embedding_json is not None

    # No rebuild/reindex call in between - the very next search sees it.
    results = index_service.search_by_image(db, b"query-photo-bytes", min_similarity=0.0)
    assert [e.id for e, _ in results] == [entry.id]


def test_second_product_added_after_the_first_search_is_also_immediately_searchable(monkeypatch):
    """Guards against the vector index only ever being built once - each
    reconcile() call must pick up rows added since the last one."""
    db = _session()
    _use_backend(monkeypatch, _FixedVectorBackend([1.0, 0.0, 0.0]))
    pipeline = IndexingPipeline()

    first = pipeline.run(
        db,
        [RawProduct(title="Product One", image_url="https://example.com/a.jpg", source="Amazon")],
        source_type=SourceType.GOOGLE_LENS,
    )
    assert first.embedded == 1
    first_results = index_service.search_by_image(db, b"photo", min_similarity=0.0)
    assert len(first_results) == 1

    second = pipeline.run(
        db,
        [RawProduct(title="Product Two", image_url="https://example.com/b.jpg", source="Amazon")],
        source_type=SourceType.GOOGLE_LENS,
    )
    assert second.embedded == 1
    second_results = index_service.search_by_image(db, b"photo", min_similarity=0.0)
    assert len(second_results) == 2


# --- IndexingResult.duration_ms ---------------------------------------------

def test_pipeline_run_stamps_a_nonnegative_duration_ms(monkeypatch):
    db = _session()
    _use_backend(monkeypatch, _FixedVectorBackend())
    pipeline = IndexingPipeline()

    result = pipeline.run(db, [RawProduct(title="Product A", source="Amazon")], source_type=SourceType.CSV)
    assert result.duration_ms >= 0
    assert result.to_dict()["duration_ms"] == result.duration_ms


def test_pipeline_run_on_empty_batch_leaves_duration_at_zero():
    db = _session()
    result = IndexingPipeline().run(db, [], source_type=SourceType.CSV)
    assert result.duration_ms == 0


# --- runner.py: live-search indexing now gets a job row --------------------

def test_index_purchase_links_in_background_creates_and_completes_a_job_row(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    test_session_local = sessionmaker(bind=engine)
    monkeypatch.setattr(runner, "SessionLocal", test_session_local)

    # No thumbnail -> no embedding attempted, keeps this test network-free.
    runner.index_purchase_links_in_background([_link()])

    db = test_session_local()
    jobs_rows = db.query(IndexingJob).all()
    assert len(jobs_rows) == 1
    job = jobs_rows[0]
    assert job.source_label == "live_search"
    assert job.source_type == SourceType.GOOGLE_LENS.value
    assert job.status == "completed"
    assert job.started_at is not None
    assert job.completed_at is not None
    assert job.completed_at >= job.started_at


def test_index_purchase_links_in_background_is_a_no_op_for_an_empty_batch(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    test_session_local = sessionmaker(bind=engine)
    monkeypatch.setattr(runner, "SessionLocal", test_session_local)

    runner.index_purchase_links_in_background([])

    db = test_session_local()
    assert db.query(IndexingJob).count() == 0


# --- index_dashboard_service: growth + indexing-time metrics ---------------

def test_growth_stats_counts_recent_products_and_builds_a_seven_day_series():
    db = _session()
    now = datetime.utcnow()
    db.add(ProductIndexEntry(product_key="a", title="A", created_at=now - timedelta(hours=1)))
    db.add(ProductIndexEntry(product_key="b", title="B", created_at=now - timedelta(days=3)))
    db.add(ProductIndexEntry(product_key="c", title="C", created_at=now - timedelta(days=20)))  # outside window
    db.commit()

    stats = dash._growth_stats(db)
    assert stats["index_growth_last_24h"] == 1
    assert stats["index_growth_last_7d"] == 2
    assert len(stats["index_growth_by_day"]) == 7
    assert sum(day["count"] for day in stats["index_growth_by_day"]) == 2


def test_growth_stats_on_an_empty_catalog_returns_a_zeroed_series():
    db = _session()
    stats = dash._growth_stats(db)
    assert stats["index_growth_last_24h"] == 0
    assert stats["index_growth_last_7d"] == 0
    assert len(stats["index_growth_by_day"]) == 7
    assert all(day["count"] == 0 for day in stats["index_growth_by_day"])


def test_indexing_time_stats_averages_completed_jobs_only():
    db = _session()
    now = datetime.utcnow()
    db.add(
        IndexingJob(
            source_type="google_lens", status="completed",
            started_at=now - timedelta(seconds=2), completed_at=now,
        )
    )
    db.add(
        IndexingJob(
            source_type="google_lens", status="completed",
            started_at=now - timedelta(seconds=4), completed_at=now,
        )
    )
    # Still running - no completed_at yet, must be excluded.
    db.add(IndexingJob(source_type="csv", status="running", started_at=now, completed_at=None))
    db.commit()

    stats = dash._indexing_time_stats(db)
    assert stats["indexing_runs_measured"] == 2
    assert stats["average_indexing_time_ms"] == pytest.approx(3000, rel=0.05)
    assert stats["average_indexing_time_by_source"]["google_lens"] == pytest.approx(3000, rel=0.05)


def test_indexing_time_stats_with_no_completed_jobs_returns_none():
    db = _session()
    stats = dash._indexing_time_stats(db)
    assert stats["average_indexing_time_ms"] is None
    assert stats["indexing_runs_measured"] == 0
    assert stats["average_indexing_time_by_source"] == {}


def test_get_index_dashboard_stats_includes_the_new_fields_without_erroring():
    db = _session()
    now = datetime.utcnow()
    db.add(ProductIndexEntry(product_key="a", title="A", created_at=now))
    db.add(
        IndexingJob(
            source_type="google_lens", source_label="live_search", status="completed",
            started_at=now - timedelta(seconds=1), completed_at=now,
        )
    )
    db.commit()

    response = dash.get_index_dashboard_stats(db)
    assert response.index_growth_last_24h == 1
    assert response.average_indexing_time_ms is not None
    assert response.indexing_runs_measured == 1
