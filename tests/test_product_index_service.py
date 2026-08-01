import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, ProductIndexEntry
from app.models import PurchaseLink
from app.services.product_index import embedding_service, service as index_service
from app.services.product_index.embedding_backends.base import EmbeddingBackend

def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()

def _link(title="Sony WH-1000XM5 Headphones", brand="Sony", platform="Amazon", price="24999", thumbnail=None):
    return PurchaseLink(
        platform=platform,
        title=title,
        brand=brand,
        price=price,
        currency="INR",
        link="https://example.com/product",
        source_domain="example.com",
        thumbnail=thumbnail,
        rating=4.5,
        review_count=120,
    )

# --- cosine similarity (pure math, no network) ---

def test_cosine_similarity_identical_vectors_is_one():
    vector = [1.0, 0.0, 1.0, 0.5]
    assert embedding_service.cosine_similarity(vector, vector) == 1.0

def test_cosine_similarity_orthogonal_vectors_is_zero():
    assert embedding_service.cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0

def test_cosine_similarity_handles_mismatched_or_empty_vectors():
    assert embedding_service.cosine_similarity([], [1.0]) == 0.0
    assert embedding_service.cosine_similarity([1.0, 2.0], [1.0]) == 0.0
    assert embedding_service.cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0

# --- upsert / catalog behavior ---

def test_upsert_product_creates_a_new_row_with_inferred_category():
    db = _session()
    entry = index_service.upsert_product(
        db, title="Nike Running Shoes Men", brand="Nike", price=2999, currency="INR", source="Amazon"
    )
    assert entry is not None
    assert entry.category == "footwear"
    assert entry.times_seen == 1

def test_upsert_product_refreshes_existing_row_instead_of_duplicating():
    db = _session()
    first = index_service.upsert_product(db, title="Sony WH-1000XM5", brand="Sony", price=24999, source="Amazon")
    second = index_service.upsert_product(db, title="Sony WH-1000XM5", brand="Sony", price=21999, source="Amazon")

    assert first.id == second.id
    assert second.price == 21999
    assert second.times_seen == 2
    assert db.query(ProductIndexEntry).count() == 1

def test_upsert_product_returns_none_for_blank_title():
    db = _session()
    assert index_service.upsert_product(db, title="   ") is None
    assert index_service.upsert_product(db, title=None) is None

def test_index_purchase_links_populates_catalog_without_network_calls():
    db = _session()
    links = [_link(title="Sony WH-1000XM5 Headphones"), _link(title="Apple AirPods Pro", brand="Apple")]
    indexed = index_service.index_purchase_links(db, links)

    assert len(indexed) == 2
    assert db.query(ProductIndexEntry).count() == 2
    # No thumbnails on these links -> no embedding fetch attempted.
    assert all(e.embedding_json is None for e in indexed)

def test_list_entries_filters_by_query_and_category():
    db = _session()
    index_service.upsert_product(db, title="Nike Running Shoes Men", brand="Nike", source="Amazon")
    index_service.upsert_product(db, title="Sony WH-1000XM5 Headphones", brand="Sony", source="Flipkart")

    rows, total = index_service.list_entries(db, query="nike")
    assert total == 1
    assert rows[0].title == "Nike Running Shoes Men"

    rows, total = index_service.list_entries(db, category="footwear")
    assert total == 1
    assert rows[0].brand == "Nike"

def test_find_similar_ranks_by_cosine_similarity():
    db = _session()
    target = index_service.upsert_product(db, title="Product A", source="Amazon")
    close = index_service.upsert_product(db, title="Product B", source="Amazon")
    far = index_service.upsert_product(db, title="Product C", source="Amazon")

    index_service._apply_embedding(target, [1.0, 0.0, 0.0])
    index_service._apply_embedding(close, [0.9, 0.1, 0.0])
    index_service._apply_embedding(far, [0.0, 1.0, 0.0])
    db.commit()

    results = index_service.find_similar(db, target.id, top_k=5)
    assert [entry.id for entry, _ in results] == [close.id, far.id]
    assert results[0][1] > results[1][1]

def test_find_similar_returns_empty_when_target_has_no_embedding():
    db = _session()
    target = index_service.upsert_product(db, title="Product A", source="Amazon")
    assert index_service.find_similar(db, target.id) == []

def test_get_stats_counts_categories_sources_and_embeddings():
    db = _session()
    a = index_service.upsert_product(db, title="Nike Running Shoes Men", brand="Nike", source="Amazon")
    index_service.upsert_product(db, title="Sony WH-1000XM5", brand="Sony", source="Flipkart")
    index_service._apply_embedding(a, [1.0, 0.0])
    db.commit()

    stats = index_service.get_stats(db)
    assert stats["total_products"] == 2
    assert stats["products_with_embeddings"] == 1
    assert stats["by_source"] == {"Amazon": 1, "Flipkart": 1}
    assert stats["by_category"] == {"footwear": 1}

# --- search_by_image / to_purchase_link (Phase 3: internal-index-first search) ---

class _FixedVectorBackend(EmbeddingBackend):
    """A deterministic, network-free stand-in for a real model: every
    upload embeds to the same fixed vector regardless of its bytes, so
    tests can control similarity purely via the catalog rows' stored
    vectors."""

    name = "fixed-vector-backend"
    dimension = 3

    def __init__(self, vector=None):
        self.vector = vector if vector is not None else [1.0, 0.0, 0.0]

    def embed(self, image_bytes: bytes) -> list[float]:
        return self.vector

class _ExplodingBackend(EmbeddingBackend):
    name = "exploding-backend"
    dimension = 3

    def embed(self, image_bytes: bytes) -> list[float]:
        raise RuntimeError("model blew up")

def _use_backend(monkeypatch, backend):
    monkeypatch.setattr(index_service.default_embedding_service, "_backend", backend)
    return backend

def test_search_by_image_ranks_catalog_by_similarity_to_the_upload(monkeypatch):
    db = _session()
    backend = _use_backend(monkeypatch, _FixedVectorBackend([1.0, 0.0, 0.0]))

    close = index_service.upsert_product(db, title="Product B", source="Amazon", attempt_embedding=False)
    far = index_service.upsert_product(db, title="Product C", source="Amazon", attempt_embedding=False)
    unembedded = index_service.upsert_product(db, title="Product D", source="Amazon", attempt_embedding=False)
    index_service._apply_embedding(close, [0.9, 0.1, 0.0], model_name=backend.name)
    index_service._apply_embedding(far, [0.0, 1.0, 0.0], model_name=backend.name)
    db.commit()

    results = index_service.search_by_image(db, b"some-uploaded-photo-bytes", min_similarity=0.0)

    ids = [entry.id for entry, _ in results]
    assert ids == [close.id, far.id]
    assert unembedded.id not in ids
    assert results[0][1] > results[1][1]

def test_search_by_image_drops_matches_below_the_similarity_floor(monkeypatch):
    db = _session()
    backend = _use_backend(monkeypatch, _FixedVectorBackend([1.0, 0.0, 0.0]))

    close = index_service.upsert_product(db, title="Product B", source="Amazon", attempt_embedding=False)
    far = index_service.upsert_product(db, title="Product C", source="Amazon", attempt_embedding=False)
    index_service._apply_embedding(close, [0.99, 0.01, 0.0], model_name=backend.name)
    index_service._apply_embedding(far, [0.0, 1.0, 0.0], model_name=backend.name)
    db.commit()

    results = index_service.search_by_image(db, b"photo", min_similarity=0.9)
    assert [entry.id for entry, _ in results] == [close.id]

def test_search_by_image_ignores_embeddings_from_a_different_backend(monkeypatch):
    db = _session()
    backend = _use_backend(monkeypatch, _FixedVectorBackend([1.0, 0.0, 0.0]))

    stale = index_service.upsert_product(db, title="Product B", source="Amazon", attempt_embedding=False)
    index_service._apply_embedding(stale, [1.0, 0.0, 0.0], model_name="some-old-backend")
    db.commit()

    assert index_service.search_by_image(db, b"photo", min_similarity=0.0) == []

def test_search_by_image_respects_top_k(monkeypatch):
    db = _session()
    backend = _use_backend(monkeypatch, _FixedVectorBackend([1.0, 0.0, 0.0]))

    for i in range(5):
        entry = index_service.upsert_product(db, title=f"Product {i}", source="Amazon", attempt_embedding=False)
        index_service._apply_embedding(entry, [1.0, 0.0, 0.0], model_name=backend.name)
    db.commit()

    results = index_service.search_by_image(db, b"photo", top_k=2, min_similarity=0.0)
    assert len(results) == 2

def test_search_by_image_returns_empty_when_embedding_the_upload_fails(monkeypatch):
    db = _session()
    _use_backend(monkeypatch, _ExplodingBackend())

    entry = index_service.upsert_product(db, title="Product A", source="Amazon", attempt_embedding=False)
    index_service._apply_embedding(entry, [1.0, 0.0, 0.0], model_name="exploding-backend")
    db.commit()

    assert index_service.search_by_image(db, b"photo") == []

def test_search_by_image_returns_empty_when_the_catalog_has_no_embeddings(monkeypatch):
    db = _session()
    _use_backend(monkeypatch, _FixedVectorBackend())
    index_service.upsert_product(db, title="Product A", source="Amazon", attempt_embedding=False)
    assert index_service.search_by_image(db, b"photo") == []

def test_search_by_image_respects_the_product_index_and_embedding_flags(monkeypatch):
    db = _session()
    backend = _use_backend(monkeypatch, _FixedVectorBackend([1.0, 0.0, 0.0]))
    entry = index_service.upsert_product(db, title="Product A", source="Amazon", attempt_embedding=False)
    index_service._apply_embedding(entry, [1.0, 0.0, 0.0], model_name=backend.name)
    db.commit()

    monkeypatch.setattr(index_service.settings, "enable_product_index", False)
    assert index_service.search_by_image(db, b"photo") == []

    monkeypatch.setattr(index_service.settings, "enable_product_index", True)
    monkeypatch.setattr(index_service.settings, "product_index_embedding_enabled", False)
    assert index_service.search_by_image(db, b"photo") == []

def test_to_purchase_link_maps_catalog_fields_and_marks_the_source_as_internal():
    db = _session()
    entry = index_service.upsert_product(
        db,
        title="Sony WH-1000XM5",
        brand="Sony",
        price=21999,
        currency="INR",
        source="Amazon",
        image_url="https://example.com/sony.jpg",
        rating=4.6,
        review_count=500,
        attempt_embedding=False,
    )

    link = index_service.to_purchase_link(entry, similarity=0.9234)

    assert isinstance(link, PurchaseLink)
    assert link.title == "Sony WH-1000XM5"
    assert link.brand == "Sony"
    assert link.price == "21999.0"
    assert link.currency == "INR"
    assert link.thumbnail == "https://example.com/sony.jpg"
    assert link.price_source == "internal_index"
    assert link.extraction_method == "internal_index_match"
    assert link.confidence_score == 0.9234

def test_to_purchase_link_handles_missing_price_and_similarity():
    db = _session()
    entry = index_service.upsert_product(db, title="Untitled Gadget", source="Amazon", attempt_embedding=False)
    link = index_service.to_purchase_link(entry)
    assert link.price is None
    assert link.confidence_score is None

def test_to_item_never_leaks_the_raw_embedding_vector():
    db = _session()
    entry = index_service.upsert_product(db, title="Product A", source="Amazon")
    index_service._apply_embedding(entry, [1.0, 0.0, 0.5])
    db.commit()

    item = index_service.to_item(entry)
    assert item.has_embedding is True
    assert item.embedding_dim == 3
    assert not hasattr(item, "embedding_json")

# --- delete_entry (FAISS-backed deletion, see vector_index.py) ---

def test_delete_entry_removes_the_row():
    db = _session()
    entry = index_service.upsert_product(db, title="Product A", source="Amazon")
    assert index_service.delete_entry(db, entry.id) is True
    assert index_service.get_entry(db, entry.id) is None
    assert db.query(ProductIndexEntry).count() == 0

def test_delete_entry_returns_false_for_an_unknown_id():
    db = _session()
    assert index_service.delete_entry(db, 999) is False

def test_delete_entry_removes_the_row_from_similarity_search_results():
    db = _session()
    target = index_service.upsert_product(db, title="Product A", source="Amazon")
    close = index_service.upsert_product(db, title="Product B", source="Amazon")
    far = index_service.upsert_product(db, title="Product C", source="Amazon")
    index_service._apply_embedding(target, [1.0, 0.0, 0.0])
    index_service._apply_embedding(close, [0.9, 0.1, 0.0])
    index_service._apply_embedding(far, [0.0, 1.0, 0.0])
    db.commit()

    # Sanity check before deleting anything.
    assert [e.id for e, _ in index_service.find_similar(db, target.id)] == [close.id, far.id]

    assert index_service.delete_entry(db, close.id) is True
    results = index_service.find_similar(db, target.id)
    assert [e.id for e, _ in results] == [far.id]

def test_to_item_json_serialization_never_leaks_the_raw_embedding_vector():
    db = _session()
    entry = index_service.upsert_product(db, title="Product A", source="Amazon")
    index_service._apply_embedding(entry, [1.0, 0.0, 0.5])
    db.commit()

    item = index_service.to_item(entry)
    dumped = json.dumps(item.model_dump(mode="json"))
    assert "1.0, 0.0, 0.5" not in dumped
