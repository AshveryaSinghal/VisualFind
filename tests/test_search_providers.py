"""
Tests for the Search Provider abstraction (app/services/search_providers/):

  * the registry (register/get/list/unregister, unknown-provider errors)
  * the built-in GoogleLensProvider adapter (identify() success shape,
    and that it wraps SerpApiError into SearchProviderError)
  * an end-to-end proof that search_service.process_image_search() is
    genuinely provider-agnostic - registering a second, unrelated
    provider and pointing settings.search_provider at it changes which
    backend answers a search with *zero* changes to search_service.py,
    which is the whole point of the abstraction.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.services import price_service, search_service
from app.services.brand_resolution.types import BrandResolutionResult
from app.services.search_providers import (
    ProviderIdentifyResult,
    SearchProvider,
    SearchProviderError,
    get_provider,
    list_providers,
    register_provider,
    unregister_provider,
)
from app.services.search_providers import google_lens as google_lens_provider
from app.services.search_providers import registry as provider_registry


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _explode_if_called(*args, **kwargs):
    raise AssertionError("Google Lens / Cloudinary should not be called when a different provider is configured")


# --- registry ---

def test_google_lens_provider_is_registered_by_default():
    assert "google_lens" in list_providers()
    assert get_provider("google_lens").display_name == "Google Lens (via SerpApi)"


def test_get_provider_falls_back_to_settings_search_provider(monkeypatch):
    monkeypatch.setattr(provider_registry.settings, "search_provider", "google_lens")
    assert get_provider().name == "google_lens"


def test_get_provider_raises_search_provider_error_for_unknown_name():
    with pytest.raises(SearchProviderError):
        get_provider("nonexistent_provider_xyz")


def test_register_provider_requires_a_name():
    class _Nameless(SearchProvider):
        name = ""

        def identify(self, image_bytes, filename):
            return ProviderIdentifyResult(candidates=[])

    with pytest.raises(ValueError):
        register_provider(_Nameless())


def test_register_and_unregister_provider_round_trip():
    class _Dummy(SearchProvider):
        name = "dummy_for_registry_test"
        display_name = "Dummy"

        def identify(self, image_bytes, filename):
            return ProviderIdentifyResult(candidates=[])

    register_provider(_Dummy())
    try:
        assert "dummy_for_registry_test" in list_providers()
        assert get_provider("dummy_for_registry_test").name == "dummy_for_registry_test"
    finally:
        unregister_provider("dummy_for_registry_test")
    assert "dummy_for_registry_test" not in list_providers()


# --- GoogleLensProvider ---

def test_google_lens_provider_identify_success(monkeypatch):
    monkeypatch.setattr(google_lens_provider, "upload_image", lambda **kwargs: "https://cdn.example.com/x.jpg")
    monkeypatch.setattr(
        google_lens_provider,
        "google_lens_search",
        lambda url: {
            "knowledge_graph": {"title": "Nike Air Max"},
            "visual_matches": [
                {"title": "Nike Air Max 90", "link": "https://amazon.in/x", "thumbnail": "https://x/thumb.jpg"}
            ],
        },
    )

    provider = google_lens_provider.GoogleLensProvider()
    result = provider.identify(b"photo-bytes", "shoe.jpg")

    assert result.provider_name == "google_lens"
    assert result.best_guess == "Nike Air Max"
    assert len(result.candidates) == 1
    assert result.candidates[0]["title"] == "Nike Air Max 90"
    assert result.raw_response["knowledge_graph"]["title"] == "Nike Air Max"


def test_google_lens_provider_wraps_serpapi_errors_in_search_provider_error(monkeypatch):
    monkeypatch.setattr(google_lens_provider, "upload_image", lambda **kwargs: "https://cdn.example.com/x.jpg")

    def _fail(url):
        raise google_lens_provider.SerpApiError("quota exceeded")

    monkeypatch.setattr(google_lens_provider, "google_lens_search", _fail)

    provider = google_lens_provider.GoogleLensProvider()
    with pytest.raises(SearchProviderError):
        provider.identify(b"photo-bytes", "shoe.jpg")


# --- end-to-end: the pipeline doesn't care which provider answers ---

def test_process_image_search_uses_whichever_provider_is_configured(monkeypatch):
    """Registers a second, totally unrelated provider, points
    settings.search_provider at it, and proves
    search_service.process_image_search() used it instead of Google Lens
    - with zero changes to search_service.py itself. Google Lens /
    Cloudinary are monkeypatched to blow up if called at all, which is
    what proves the swap genuinely bypassed them rather than merely also
    calling this stub."""

    class _StubProvider(SearchProvider):
        name = "stub_visual_search_for_test"
        display_name = "Stub Visual Search"

        def identify(self, image_bytes, filename):
            return ProviderIdentifyResult(
                candidates=[
                    {
                        "title": "Stub Running Shoe",
                        "link": "https://www.amazon.in/dp/stub123",
                        "price": None,
                        "currency": None,
                        "thumbnail": "https://cdn.example.com/stub.jpg",
                        "bucket": "products",
                    }
                ],
                best_guess="Stub Running Shoe",
                raw_response={},
                provider_name=self.name,
            )

    register_provider(_StubProvider())
    monkeypatch.setattr(provider_registry.settings, "search_provider", "stub_visual_search_for_test")

    # If anything still reaches Google Lens / Cloudinary, fail loudly.
    monkeypatch.setattr(google_lens_provider, "upload_image", _explode_if_called)
    monkeypatch.setattr(google_lens_provider, "google_lens_search", _explode_if_called)

    # Not under test here - stub out the rest of the pipeline exactly like
    # tests/test_search_service_internal_index.py does for Lens itself, so
    # this test is fast, offline, and focused on provider selection.
    monkeypatch.setattr(price_service, "fetch_offers_for_query", lambda query, db: [])
    monkeypatch.setattr(
        price_service,
        "enrich_with_live_prices",
        lambda trusted_candidates, query, db, offers=None: [
            {**c, "price_source": "stub", "extraction_method": "stub", "confidence_score": 1.0}
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
    monkeypatch.setattr(search_service.settings, "enable_internal_index_search", False)

    db = _session()
    try:
        response = search_service.process_image_search(b"photo-bytes", "shoe.jpg", db)
    finally:
        unregister_provider("stub_visual_search_for_test")

    assert response.results
    assert response.results[0].title == "Stub Running Shoe"
    assert response.results[0].platform == "Amazon"
