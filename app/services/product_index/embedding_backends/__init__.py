"""
Registry of available embedding backends, keyed by `EmbeddingBackend.name`.

Swapping the model VisualFind uses for product-image embeddings is meant
to be a config change, not a code change everywhere: implement a new
`EmbeddingBackend`, `register_backend(...)` it (or add it to `_REGISTRY`
below), and point `settings.product_index_embedding_backend` at its name.
"""

from app.config import settings

from .base import EmbeddingBackend
from .open_clip_backend import OpenClipEmbeddingBackend
from .perceptual_hash import PerceptualHashEmbeddingBackend

_REGISTRY: dict[str, type[EmbeddingBackend]] = {
    PerceptualHashEmbeddingBackend.name: PerceptualHashEmbeddingBackend,
    # Registered by class, not instance, so importing this module never
    # requires torch/open_clip_torch to be installed - only actually
    # selecting this backend (settings.product_index_embedding_backend
    # pointed at its name) instantiates it, which is where
    # open_clip_backend.py's lazy import + friendly ImportError live.
    "open-clip-vit-b-32": OpenClipEmbeddingBackend,
}

def register_backend(backend_cls: type[EmbeddingBackend]) -> None:
    """Adds (or replaces) an entry in the backend registry. Call this once,
    e.g. at app startup, to make a new model available - then flip
    `settings.product_index_embedding_backend` to its `name` to actually
    switch to it."""
    _REGISTRY[backend_cls.name] = backend_cls

def available_backends() -> list[str]:
    return sorted(_REGISTRY.keys())

def get_backend(name: str | None = None) -> EmbeddingBackend:
    """Resolves the backend to use - `name` if given, otherwise whatever
    `settings.product_index_embedding_backend` currently says. Raises
    ValueError for an unregistered name rather than silently falling back,
    since that almost always means a typo'd config value."""
    resolved_name = name or settings.product_index_embedding_backend
    try:
        backend_cls = _REGISTRY[resolved_name]
    except KeyError:
        raise ValueError(
            f"Unknown embedding backend '{resolved_name}'. Registered backends: {available_backends()}"
        )
    return backend_cls()

__all__ = ["EmbeddingBackend", "register_backend", "available_backends", "get_backend"]
