from app.database import ProductIndexEntry
from app.services.product_index.embedding_backends.base import EmbeddingBackend
from app.services.product_index.embedding_service import EmbeddingService

class FakeBackend(EmbeddingBackend):
    """A deterministic, network-free stand-in for a real model: turns the
    image bytes' length into a tiny vector, so tests can assert on it
    without downloading or decoding a real image."""

    name = "fake-backend-v1"
    dimension = 2

    def __init__(self):
        self.embed_calls = 0

    def embed(self, image_bytes: bytes) -> list[float]:
        self.embed_calls += 1
        return [float(len(image_bytes)), 1.0]

class ExplodingBackend(EmbeddingBackend):
    name = "exploding-backend"
    dimension = 1

    def embed(self, image_bytes: bytes) -> list[float]:
        raise RuntimeError("model blew up")

def _entry(**overrides) -> ProductIndexEntry:
    defaults = dict(
        product_key="k",
        title="Product",
        image_url="https://example.com/product.jpg",
    )
    defaults.update(overrides)
    return ProductIndexEntry(**defaults)

def _service_with_fake_download(backend, image_bytes=b"fake-image-bytes"):
    service = EmbeddingService(backend=backend, timeout=1.0)
    service.download_image = lambda url: image_bytes
    return service

# --- needs_embedding: the "avoid recomputing" rule ---

def test_needs_embedding_true_for_a_fresh_entry():
    service = EmbeddingService(backend=FakeBackend())
    assert service.needs_embedding(_entry()) is True

def test_needs_embedding_false_once_embedded_by_the_active_backend():
    backend = FakeBackend()
    service = _service_with_fake_download(backend)
    entry = _entry()

    assert service.embed_product(entry) is True
    assert service.needs_embedding(entry) is False

def test_needs_embedding_true_after_backend_is_swapped():
    old_backend = FakeBackend()
    entry = _entry(embedding_json="[1.0, 1.0]", embedding_dim=2, embedding_model=old_backend.name)

    new_backend = FakeBackend()
    new_backend.name = "fake-backend-v2"
    service = EmbeddingService(backend=new_backend)

    assert service.needs_embedding(entry) is True

# --- embed_product: download -> embed -> store, and skip cases ---

def test_embed_product_downloads_embeds_and_stores_on_the_entry():
    backend = FakeBackend()
    service = _service_with_fake_download(backend, image_bytes=b"0123456789")
    entry = _entry()

    updated = service.embed_product(entry)

    assert updated is True
    assert entry.embedding_json == "[10.0, 1.0]"
    assert entry.embedding_dim == 2
    assert entry.embedding_model == "fake-backend-v1"
    assert backend.embed_calls == 1

def test_embed_product_skips_recompute_for_an_already_embedded_entry():
    backend = FakeBackend()
    service = _service_with_fake_download(backend)
    entry = _entry()

    assert service.embed_product(entry) is True
    assert service.embed_product(entry) is False
    # Only the first call should have actually invoked the model.
    assert backend.embed_calls == 1

def test_embed_product_returns_false_without_an_image_url():
    service = _service_with_fake_download(FakeBackend())
    entry = _entry(image_url=None)
    assert service.embed_product(entry) is False

def test_embed_product_returns_false_when_download_fails():
    service = EmbeddingService(backend=FakeBackend())
    service.download_image = lambda url: None
    entry = _entry()
    assert service.embed_product(entry) is False
    assert entry.embedding_json is None

def test_embed_product_returns_false_and_does_not_raise_when_backend_errors():
    service = _service_with_fake_download(ExplodingBackend())
    entry = _entry()
    assert service.embed_product(entry) is False
    assert entry.embedding_json is None

def test_embed_product_respects_the_embedding_enabled_flag(monkeypatch):
    from app.services.product_index import embedding_service as embedding_service_module

    monkeypatch.setattr(embedding_service_module.settings, "product_index_embedding_enabled", False)
    service = _service_with_fake_download(FakeBackend())
    entry = _entry()
    assert service.embed_product(entry) is False

# --- cosine_similarity ---

def test_cosine_similarity_identical_vectors_is_one():
    from app.services.product_index.embedding_service import cosine_similarity

    vector = [1.0, 0.0, 1.0, 0.5]
    assert cosine_similarity(vector, vector) == 1.0

def test_cosine_similarity_handles_mismatched_or_empty_vectors():
    from app.services.product_index.embedding_service import cosine_similarity

    assert cosine_similarity([], [1.0]) == 0.0
    assert cosine_similarity([1.0, 2.0], [1.0]) == 0.0
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0

# --- backend registry ---

def test_get_backend_resolves_the_default_perceptual_hash_backend():
    from app.services.product_index.embedding_backends import get_backend

    backend = get_backend("perceptual-hash-v1")
    assert backend.name == "perceptual-hash-v1"
    assert backend.dimension == 8 * 8 + 4**3

def test_get_backend_raises_for_an_unregistered_name():
    import pytest

    from app.services.product_index.embedding_backends import get_backend

    with pytest.raises(ValueError):
        get_backend("does-not-exist")

def test_register_backend_makes_a_new_backend_resolvable_by_name():
    from app.services.product_index.embedding_backends import get_backend, register_backend

    class NewBackend(EmbeddingBackend):
        name = "test-only-backend"
        dimension = 3

        def embed(self, image_bytes: bytes) -> list[float]:
            return [0.0, 0.0, 0.0]

    register_backend(NewBackend)
    backend = get_backend("test-only-backend")
    assert isinstance(backend, NewBackend)
