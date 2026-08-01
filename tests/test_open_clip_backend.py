"""
Tests for OpenClipEmbeddingBackend
(app/services/product_index/embedding_backends/open_clip_backend.py).

torch / open_clip_torch are an optional dependency NOT installed in this
test environment (see requirements-openclip.txt) - by design, importing
open_clip_backend.py must never require them (only instantiating the
backend does). So instead of skipping backend-logic tests when the real
packages are absent, these tests install minimal fake `torch`/`open_clip`
modules into `sys.modules` and exercise the real backend code against
them. That's a real test of `_ensure_loaded()`'s caching, `embed()`'s
tensor pipeline, and the friendly-ImportError path - not a mock of the
backend itself.
"""

import math
import sys

import pytest

from app.services.product_index.embedding_backends import get_backend
from app.services.product_index.embedding_backends.open_clip_backend import (
    OpenClipEmbeddingBackend,
)

# --- Minimal fake torch/open_clip, just enough surface area for embed() ---

class _FakeTensor:
    """Always holds a *batch*: a list of one-or-more equal-length vectors."""

    def __init__(self, batch: list[list[float]]):
        self.batch = batch

    def unsqueeze(self, dim):
        assert dim == 0
        return _FakeTensor([self.batch]) if not isinstance(self.batch[0], list) else self

    def to(self, device):
        return self

    def norm(self, dim=-1, keepdim=True):
        return _FakeTensor([[math.sqrt(sum(v * v for v in row))] for row in self.batch])

    def __truediv__(self, other):
        return _FakeTensor(
            [[v / scale[0] for v in row] for row, scale in zip(self.batch, other.batch)]
        )

    def squeeze(self, dim):
        assert dim == 0
        return _FakeTensor(self.batch[0])

    def cpu(self):
        return self

    def tolist(self):
        return self.batch

class _FakeModel:
    def __init__(self, output_batch):
        self._output_batch = output_batch
        self.eval_called = False
        self.device = None

    def to(self, device):
        self.device = device
        return self

    def eval(self):
        self.eval_called = True

    def encode_image(self, tensor):
        return _FakeTensor(self._output_batch)

class _FakeNoGrad:
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

def _install_fake_open_clip(monkeypatch, output_batch=None):
    """Installs fake `open_clip`/`torch` modules and returns the fake model
    (pre-`encode_image` output configurable via `output_batch`)."""
    output_batch = output_batch or [[3.0, 4.0, 0.0]]  # norm == 5 -> [0.6, 0.8, 0.0]
    fake_model = _FakeModel(output_batch)

    fake_open_clip = type(sys)("open_clip")
    fake_open_clip.create_model_and_transforms = lambda model_name, pretrained: (
        fake_model,
        None,
        lambda img: _FakeTensor([1.0, 2.0, 3.0]),  # a single (non-batched) preprocessed vector
    )

    fake_torch = type(sys)("torch")
    fake_torch.no_grad = lambda: _FakeNoGrad()

    monkeypatch.setitem(sys.modules, "open_clip", fake_open_clip)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    return fake_model

@pytest.fixture(autouse=True)
def _reset_model_cache():
    """`OpenClipEmbeddingBackend` caches the loaded model at the class
    level by design (see its docstring) - reset that shared state before
    each test so tests don't leak a fake model into one another."""
    OpenClipEmbeddingBackend._loaded_key = None
    OpenClipEmbeddingBackend._loaded_model = None
    OpenClipEmbeddingBackend._loaded_preprocess = None
    yield
    OpenClipEmbeddingBackend._loaded_key = None
    OpenClipEmbeddingBackend._loaded_model = None
    OpenClipEmbeddingBackend._loaded_preprocess = None

def _tiny_jpeg_bytes() -> bytes:
    from io import BytesIO

    from PIL import Image

    buf = BytesIO()
    Image.new("RGB", (4, 4), color=(10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()

# --- Registry wiring ---

def test_get_backend_resolves_the_open_clip_backend_by_name():
    backend = get_backend("open-clip-vit-b-32")
    assert isinstance(backend, OpenClipEmbeddingBackend)
    assert backend.name == "open-clip-vit-b-32"

def test_default_model_maps_to_the_known_512_dim_vit_b_32_dimension():
    backend = OpenClipEmbeddingBackend(model_name="ViT-B-32")
    assert backend.dimension == 512

def test_a_different_model_name_changes_both_name_and_dimension():
    backend = OpenClipEmbeddingBackend(model_name="ViT-L-14", pretrained="openai")
    assert backend.name == "open-clip-vit-l-14"
    assert backend.dimension == 768

# --- Friendly ImportError when torch/open_clip aren't installed ---

def test_embed_raises_a_clear_importerror_when_dependencies_are_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "open_clip", None)
    monkeypatch.setitem(sys.modules, "torch", None)

    backend = OpenClipEmbeddingBackend()
    with pytest.raises(ImportError, match="requirements-openclip.txt"):
        backend.embed(_tiny_jpeg_bytes())

# --- embed(): the real tensor pipeline, against fakes ---

def test_embed_returns_an_l2_normalized_vector(monkeypatch):
    _install_fake_open_clip(monkeypatch, output_batch=[[3.0, 4.0, 0.0]])

    backend = OpenClipEmbeddingBackend()
    vector = backend.embed(_tiny_jpeg_bytes())

    assert vector == pytest.approx([0.6, 0.8, 0.0])
    norm = math.sqrt(sum(v * v for v in vector))
    assert norm == pytest.approx(1.0)

def test_embed_updates_dimension_to_match_the_real_model_output(monkeypatch):
    _install_fake_open_clip(monkeypatch, output_batch=[[1.0, 0.0]])  # only 2 dims

    backend = OpenClipEmbeddingBackend()
    assert backend.dimension == 512  # the ViT-B-32 guess, before the model has run

    vector = backend.embed(_tiny_jpeg_bytes())

    assert len(vector) == 2
    assert backend.dimension == 2  # corrected to reality after running

def test_model_is_loaded_once_and_reused_across_instances(monkeypatch):
    fake_model = _install_fake_open_clip(monkeypatch)

    first = OpenClipEmbeddingBackend()
    first.embed(_tiny_jpeg_bytes())
    assert fake_model.eval_called is True

    # A second instance with the same (model_name, pretrained) should reuse
    # the already-loaded model rather than calling create_model_and_transforms
    # again - simulate that by making a second call blow up if it's hit.
    import open_clip as fake_open_clip_module  # the fake installed above

    def _explode(*args, **kwargs):
        raise AssertionError("create_model_and_transforms should not be called again")

    fake_open_clip_module.create_model_and_transforms = _explode

    second = OpenClipEmbeddingBackend()
    vector = second.embed(_tiny_jpeg_bytes())
    assert vector == pytest.approx([0.6, 0.8, 0.0])

# --- needs_embedding integration: swapping to/from this backend ---

def test_swapping_from_perceptual_hash_to_open_clip_makes_needs_embedding_true():
    from app.database import ProductIndexEntry
    from app.services.product_index.embedding_service import EmbeddingService

    entry = ProductIndexEntry(
        product_key="k",
        title="Product",
        image_url="https://example.com/product.jpg",
        embedding_json="[1.0, 1.0]",
        embedding_dim=2,
        embedding_model="perceptual-hash-v1",
    )
    service = EmbeddingService(backend=OpenClipEmbeddingBackend())
    assert service.needs_embedding(entry) is True
