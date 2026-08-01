"""
Google Lens (via the configured Search Provider - see
app/services/search_providers/) is always the primary, trusted pipeline
for an image search and always runs. VisualFind's own Product Index is,
at most, a supplemental source of a few extra "also in our catalog"
recommendations appended *after* Lens's results - it never answers a
search on its own, never short-circuits the Lens call, and never
influences best-deal selection. See
app/services/search_service.py::process_image_search and
::_supplement_with_internal_index.

A stub SearchProvider stands in for Google Lens/Cloudinary here (same
pattern as tests/test_search_providers.py) so these tests are fast,
offline, and don't depend on real network calls.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.services import price_service, search_service
from app.services.brand_resolution.types import BrandResolutionResult
from app.services.product_index import service as index_service
from app.services.product_index.embedding_backends.base import EmbeddingBackend
from app.services.search_providers import (
    ProviderIdentifyResult,
    SearchProvider,
    register_provider,
    unregister_provider,
)
from app.services.search_providers import registry as provider_registry


class _FixedVectorBackend(EmbeddingBackend):
    """Every uploaded image embeds to the same fixed vector, regardless of
    its actual bytes - lets tests control similarity purely via the
    catalog rows' stored vectors, with no real image decoding involved."""

    name = "fixed-vector-backend"
    dimension = 3

    def __init__(self, vector=None):
        self.vector = vector if vector is not None else [1.0, 0.0, 0.0]

    def embed(self, image_bytes: bytes) -> list[float]:
        return self.vector


class _StubLensProvider(SearchProvider):
    """Stands in for the real Google Lens provider: always returns one
    trusted candidate, so every test has a deterministic, Lens-sourced
    "primary" result to check the internal index never displaces."""

    name = "stub_lens_for_internal_index_test"
    display_name = "Stub Lens"

    def identify(self, image_bytes: bytes, filename: str) -> ProviderIdentifyResult:
        return ProviderIdentifyResult(
            candidates=[
                {
                    "title": "Lens Primary Sneaker",
                    "link": "https://www.amazon.in/dp/lens-primary",
                    "price": None,
                    "currency": None,
                    "thumbnail": "https://cdn.example.com/lens-primary.jpg",
                    "bucket": "products",
                }
            ],
            best_guess="Lens Primary Sneaker",
            raw_response={},
            provider_name=self.name,
        )


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _seed_catalog_entry(db, backend, *, title, vector, price=1999, source="Amazon"):
    entry = index_service.upsert_product(
        db, title=title, brand="TestBrand", price=price, currency="INR", source=source,
        image_url="https://example.com/x.jpg", rating=4.2, review_count=50,
        attempt_embedding=False,
    )
    index_service._apply_embedding(entry, vector, model_name=backend.name)
    db.commit()
    return entry


@pytest.fixture
def lens_stubbed(monkeypatch):
    """Wires the stub Lens provider in as the active provider, and stubs
    out the rest of the live pipeline (pricing, brand resolution) exactly
    like tests/test_search_providers.py does, so the primary Lens path is
    fast, offline, and deterministic."""
    register_provider(_StubLensProvider())
    monkeypatch.setattr(provider_registry.settings, "search_provider", _StubLensProvider.name)
    monkeypatch.setattr(price_service, "fetch_offers_for_query", lambda query, db: [])
    monkeypatch.setattr(
        price_service,
        "enrich_with_live_prices",
        lambda trusted_candidates, query, db, offers=None: [
            {**c, "price": "1499", "price_source": "stub", "extraction_method": "stub", "confidence_score": 1.0}
            for c in trusted_candidates
        ],
    )
    monkeypatch.setattr(
        search_service._brand_resolution_service,
        "resolve",
        lambda lens_response, candidates, query, offers=None: BrandResolutionResult(
            detected_brand=None, brand_confidence=0.0
        ),
    )
    try:
        yield
    finally:
        unregister_provider(_StubLensProvider.name)


@pytest.fixture
def internal_index_ready(monkeypatch):
    """Wires the fixed-vector backend into the product index singleton and
    enables + lowers the internal-index thresholds so a catalog seeded in
    a test reliably qualifies as a supplemental match."""
    backend = _FixedVectorBackend([1.0, 0.0, 0.0])
    monkeypatch.setattr(index_service.default_embedding_service, "_backend", backend)
    monkeypatch.setattr(search_service.settings, "enable_product_index", True)
    monkeypatch.setattr(search_service.settings, "enable_internal_index_search", True)
    monkeypatch.setattr(search_service.settings, "product_index_search_min_matches", 1)
    monkeypatch.setattr(search_service.settings, "product_index_search_min_similarity", 0.8)
    monkeypatch.setattr(search_service.settings, "internal_index_max_supplemental_results", 5)
    return backend


def test_google_lens_result_is_always_present_even_with_plenty_of_internal_matches(
    lens_stubbed, internal_index_ready
):
    """The whole point of the fix: Lens is primary and always answers,
    regardless of how many qualifying matches the internal index has."""
    backend = internal_index_ready
    db = _session()
    _seed_catalog_entry(db, backend, title="Catalog Product A", vector=[0.95, 0.05, 0.0])
    _seed_catalog_entry(db, backend, title="Catalog Product B", vector=[0.9, 0.1, 0.0])
    _seed_catalog_entry(db, backend, title="Catalog Product C", vector=[0.92, 0.08, 0.0])

    response = search_service.process_image_search(b"uploaded-photo-bytes", "photo.jpg", db)

    titles = [r.title for r in response.results]
    assert "Lens Primary Sneaker" in titles
    log = db.query(search_service.SearchLog).filter_by(id=response.search_id).first()
    assert log.query_source != "internal_index"


def test_internal_index_results_are_appended_after_lens_as_supplemental_recommendations(
    lens_stubbed, internal_index_ready
):
    backend = internal_index_ready
    db = _session()
    _seed_catalog_entry(db, backend, title="Catalog Product A", vector=[0.95, 0.05, 0.0])
    _seed_catalog_entry(db, backend, title="Catalog Product B", vector=[0.9, 0.1, 0.0])

    response = search_service.process_image_search(b"uploaded-photo-bytes", "photo.jpg", db)

    assert response.results[0].title == "Lens Primary Sneaker"
    supplemental = [r for r in response.results if r.price_source == "internal_index"]
    assert len(supplemental) == 2
    assert "index" in response.note.lower()

    log = db.query(search_service.SearchLog).filter_by(id=response.search_id).first()
    assert log.query_source is not None and log.query_source.endswith("+index_supplement")


def test_internal_index_never_displaces_the_best_deal_chosen_from_lens_results(
    lens_stubbed, internal_index_ready
):
    """Even if a catalog item is cheaper, best-deal selection must stay
    anchored to Lens's own (trusted) results - the index is only ever an
    extra suggestion, never authoritative."""
    backend = internal_index_ready
    db = _session()
    _seed_catalog_entry(db, backend, title="Much Cheaper Catalog Item", vector=[0.95, 0.05, 0.0], price=1)

    response = search_service.process_image_search(b"uploaded-photo-bytes", "photo.jpg", db)

    best_deal = next((r for r in response.results if r.is_best_deal), None)
    assert best_deal is not None
    assert best_deal.title == "Lens Primary Sneaker"


def test_internal_index_supplement_is_capped(lens_stubbed, internal_index_ready, monkeypatch):
    monkeypatch.setattr(search_service.settings, "internal_index_max_supplemental_results", 2)
    backend = internal_index_ready
    db = _session()
    for i in range(5):
        _seed_catalog_entry(db, backend, title=f"Catalog Product {i}", vector=[0.95, 0.05, 0.0])

    response = search_service.process_image_search(b"uploaded-photo-bytes", "photo.jpg", db)

    supplemental = [r for r in response.results if r.price_source == "internal_index"]
    assert len(supplemental) == 2


def test_internal_index_supplement_deduplicates_against_lens_results(lens_stubbed, internal_index_ready):
    """A catalog row that's really the same product Lens already returned
    shouldn't be listed a second time."""
    backend = internal_index_ready
    db = _session()
    _seed_catalog_entry(db, backend, title="Lens Primary Sneaker", vector=[0.95, 0.05, 0.0], source="Amazon")
    _seed_catalog_entry(db, backend, title="Genuinely Different Product", vector=[0.9, 0.1, 0.0])

    response = search_service.process_image_search(b"uploaded-photo-bytes", "photo.jpg", db)

    titles = [r.title for r in response.results]
    assert titles.count("Lens Primary Sneaker") == 1
    assert "Genuinely Different Product" in titles


def test_internal_index_supplement_skipped_when_disabled(lens_stubbed, monkeypatch):
    backend = _FixedVectorBackend([1.0, 0.0, 0.0])
    monkeypatch.setattr(index_service.default_embedding_service, "_backend", backend)
    monkeypatch.setattr(search_service.settings, "enable_internal_index_search", False)

    db = _session()
    _seed_catalog_entry(db, backend, title="Catalog Product A", vector=[0.95, 0.05, 0.0])
    _seed_catalog_entry(db, backend, title="Catalog Product B", vector=[0.9, 0.1, 0.0])

    response = search_service.process_image_search(b"uploaded-photo-bytes", "photo.jpg", db)

    assert all(r.price_source != "internal_index" for r in response.results)
    assert len(response.results) == 1
    assert response.results[0].title == "Lens Primary Sneaker"
