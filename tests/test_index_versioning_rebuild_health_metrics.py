"""
Tests for the Phase 5 scalability additions: index versioning, full index
rebuild, index health monitoring, and search latency metrics.

Network-free throughout: embedding computation is stubbed via a fixed-
vector backend (same pattern as test_product_index_service.py) and
download_image is monkeypatched so no real HTTP call is made for entries
with an image_url.
"""

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, IndexingJob, IndexVersion, ProductIndexEntry, SearchLog
from app.services import index_health_service, search_metrics_service
from app.services.indexing import rebuild as rebuild_service
from app.services.indexing import versioning
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
    monkeypatch.setattr(index_service.default_embedding_service, "_backend", backend)
    monkeypatch.setattr(rebuild_service.default_embedding_service, "_backend", backend)
    return backend


def _stub_downloads(monkeypatch):
    """Every entry with an image_url 'downloads' successfully without a
    real network call."""
    monkeypatch.setattr(
        rebuild_service.default_embedding_service, "download_image", lambda url: b"fake-bytes"
    )


# --- versioning.py ---

def test_start_version_assigns_sequential_version_numbers():
    db = _session()
    v1 = versioning.start_version(db, label="first")
    v2 = versioning.start_version(db, label="second")
    assert v1.version_number == 1
    assert v2.version_number == 2
    assert v1.status == "building"


def test_finish_version_success_activates_and_archives_previous():
    db = _session()
    v1 = versioning.start_version(db)
    versioning.finish_version_success(db, v1.id, total_entries=5, embedded_entries=5, failed_entries=0)

    v2 = versioning.start_version(db)
    versioning.finish_version_success(db, v2.id, total_entries=6, embedded_entries=6, failed_entries=0)

    db.refresh(v1)
    db.refresh(v2)
    assert v1.status == "archived"
    assert v2.status == "active"
    assert versioning.get_active_version(db).id == v2.id


def test_finish_version_failed_marks_status_and_error():
    db = _session()
    v1 = versioning.start_version(db)
    versioning.finish_version_failed(db, v1.id, "boom")
    db.refresh(v1)
    assert v1.status == "failed"
    assert "boom" in v1.error_message


def test_list_versions_orders_newest_first():
    db = _session()
    versioning.start_version(db, label="a")
    versioning.start_version(db, label="b")
    versions = versioning.list_versions(db)
    assert [v.label for v in versions] == ["b", "a"]


# --- rebuild.py ---

def test_rebuild_index_embeds_all_entries_and_activates_a_version(monkeypatch):
    db = _session()
    backend = _use_backend(monkeypatch, _FixedVectorBackend([1.0, 0.0, 0.0]))
    _stub_downloads(monkeypatch)

    index_service.upsert_product(
        db, title="  nike   running shoes  ", brand="", price=2999, source="Amazon",
        image_url="https://example.com/a.jpg",
    )
    index_service.upsert_product(
        db, title="Sony WH-1000XM5", brand="Sony", price=24999, source="Flipkart",
        image_url="https://example.com/b.jpg",
    )
    db.commit()

    result = rebuild_service.rebuild_index(db, full_reembed=True, renormalize=True, triggered_by="test")

    assert result.status == "active"
    assert result.total_entries == 2
    assert result.re_embedded == 2
    assert result.embedding_failed == 0

    entries = db.query(ProductIndexEntry).all()
    assert all(e.embedding_model == backend.name for e in entries)
    assert all(e.index_version == result.version_number for e in entries)

    active = versioning.get_active_version(db)
    assert active.version_number == result.version_number
    assert active.status == "active"


def test_rebuild_index_full_reembed_recomputes_even_current_embeddings(monkeypatch):
    db = _session()
    backend = _use_backend(monkeypatch, _FixedVectorBackend([1.0, 0.0, 0.0]))
    _stub_downloads(monkeypatch)

    entry = index_service.upsert_product(
        db, title="Nike Shoes", source="Amazon", image_url="https://example.com/a.jpg"
    )
    index_service._apply_embedding(entry, [0.5, 0.5, 0.0], model_name=backend.name)
    db.commit()

    # needs_embedding would say False here (already current) - full_reembed
    # must force it anyway.
    assert index_service.default_embedding_service.needs_embedding(entry) is False

    result = rebuild_service.rebuild_index(db, full_reembed=True, renormalize=False)
    assert result.re_embedded == 1
    db.refresh(entry)
    assert json.loads(entry.embedding_json) == [1.0, 0.0, 0.0]


def test_rebuild_index_catch_up_only_touches_entries_needing_embedding(monkeypatch):
    db = _session()
    backend = _use_backend(monkeypatch, _FixedVectorBackend([1.0, 0.0, 0.0]))
    _stub_downloads(monkeypatch)

    already_current = index_service.upsert_product(
        db, title="Nike Shoes", source="Amazon", image_url="https://example.com/a.jpg",
        attempt_embedding=False,
    )
    index_service._apply_embedding(already_current, [0.5, 0.5, 0.0], model_name=backend.name)
    missing = index_service.upsert_product(
        db, title="Sony Headphones", source="Amazon", image_url="https://example.com/b.jpg",
        attempt_embedding=False,
    )
    db.commit()
    assert missing.embedding_json is None

    result = rebuild_service.rebuild_index(db, full_reembed=False, renormalize=False)

    assert result.re_embedded == 1
    db.refresh(already_current)
    db.refresh(missing)
    # untouched - was already current
    assert json.loads(already_current.embedding_json) == [0.5, 0.5, 0.0]
    # newly embedded
    assert json.loads(missing.embedding_json) == [1.0, 0.0, 0.0]


def test_rebuild_index_renormalizes_titles():
    db = _session()
    entry = index_service.upsert_product(db, title="nike running shoes", brand="Nike", source="Amazon")
    entry.title = "  nike    running   shoes  "
    db.commit()

    result = rebuild_service.rebuild_index(db, full_reembed=False, renormalize=True)
    assert result.renormalized >= 1
    db.refresh(entry)
    assert entry.title == "nike running shoes"


def test_rebuild_index_disabled_product_index_fails_the_version(monkeypatch):
    db = _session()
    monkeypatch.setattr(rebuild_service.settings, "enable_product_index", False)
    result = rebuild_service.rebuild_index(db)
    assert result.status == "failed"
    version = versioning.get_version(db, result.version_id)
    assert version.status == "failed"


# --- index_health_service.py ---

def test_health_check_is_healthy_for_a_freshly_rebuilt_fully_embedded_catalog(monkeypatch):
    db = _session()
    _use_backend(monkeypatch, _FixedVectorBackend())
    _stub_downloads(monkeypatch)

    index_service.upsert_product(db, title="Nike Shoes", source="Amazon", image_url="https://example.com/a.jpg")
    db.commit()
    rebuild_service.rebuild_index(db, full_reembed=True)

    result = index_health_service.run_health_check(db, persist=True)
    assert result["status"] == "healthy"
    check_names = {c["name"] for c in result["checks"]}
    assert {
        "product_index_enabled", "embedding_coverage", "stale_embeddings",
        "index_version", "recent_job_failures", "search_latency",
    } <= check_names

    history = index_health_service.list_health_history(db)
    assert len(history) == 1
    assert history[0]["status"] == "healthy"


def test_health_check_flags_low_embedding_coverage():
    db = _session()
    for i in range(10):
        index_service.upsert_product(db, title=f"Product {i}", source="Amazon")
    db.commit()

    result = index_health_service.run_health_check(db, persist=False)
    coverage_check = next(c for c in result["checks"] if c["name"] == "embedding_coverage")
    assert coverage_check["status"] == "unhealthy"
    assert result["status"] == "unhealthy"


def test_health_check_flags_no_active_version_as_degraded():
    db = _session()
    result = index_health_service.run_health_check(db, persist=False)
    version_check = next(c for c in result["checks"] if c["name"] == "index_version")
    assert version_check["status"] == "degraded"


def test_health_check_flags_recent_job_failures():
    db = _session()
    for i in range(4):
        db.add(IndexingJob(source_type="csv", status="failed" if i < 2 else "completed"))
    db.commit()

    result = index_health_service.run_health_check(db, persist=False)
    job_check = next(c for c in result["checks"] if c["name"] == "recent_job_failures")
    assert job_check["details"]["failed_jobs"] == 2
    assert job_check["status"] in ("degraded", "unhealthy")


# --- search_metrics_service.py ---

def test_search_latency_metrics_computes_percentiles_and_excludes_cache():
    db = _session()
    for ms in [100, 200, 300, 400, 500]:
        db.add(SearchLog(image_filename="x.jpg", query_source="internal_index", execution_time_ms=ms))
    db.add(SearchLog(image_filename="x.jpg", query_source="cache", execution_time_ms=0))
    db.commit()

    metrics = search_metrics_service.get_search_latency_metrics(db)
    assert metrics["sample_size"] == 6
    assert metrics["cache_hits"] == 1
    assert metrics["live_searches"] == 5
    assert metrics["average_latency_ms"] == 300.0
    assert metrics["min_latency_ms"] == 100
    assert metrics["max_latency_ms"] == 500
    assert metrics["p50_latency_ms"] == 300
    assert "internal_index" in metrics["by_query_source"]
    assert "cache" in metrics["by_query_source"]


def test_search_latency_metrics_handles_no_data():
    db = _session()
    metrics = search_metrics_service.get_search_latency_metrics(db)
    assert metrics["sample_size"] == 0
    assert metrics["average_latency_ms"] is None
    assert metrics["p95_latency_ms"] is None
