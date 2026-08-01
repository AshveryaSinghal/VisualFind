"""
The swap point for embedding models.

`EmbeddingService` (see ../embedding_service.py) never touches pixels or
model weights directly - it only ever calls `.embed(image_bytes)` on
whatever `EmbeddingBackend` is currently configured. To move VisualFind
from this lightweight perceptual-hash backend to a real deep-learning
model (CLIP, a ViT, a hosted embeddings API, ...), write one new class
implementing this interface and register it - no other file in the app
needs to change.
"""

from abc import ABC, abstractmethod

class EmbeddingBackend(ABC):
    """One embedding model.

    `name` must be a short, stable identifier for this backend/version
    (e.g. "perceptual-hash-v1", "clip-vit-b32"). It's stored alongside
    every embedding it produces (`ProductIndexEntry.embedding_model`) so
    the app can tell which vectors came from which model - vectors from
    different backends are never comparable to each other, and this is
    exactly how `EmbeddingService.needs_embedding` decides whether an
    existing embedding is stale after a backend swap.
    """

    name: str
    dimension: int

    @abstractmethod
    def embed(self, image_bytes: bytes) -> list[float]:
        """Turns raw image bytes into a fixed-length (`self.dimension`)
        embedding vector. Implementations should raise on failure (bad
        image, model error, etc.) rather than returning None/partial data -
        `EmbeddingService` is responsible for catching and logging that,
        not this method.
        """
        raise NotImplementedError
