"""
The Embedding Service.

This is the one place in the app that turns a product image into a stored
vector. It is responsible for, and only for:

  1. Downloading the product image.
  2. Generating an embedding for it, via whichever `EmbeddingBackend` is
     currently configured (see embedding_backends/ - that's the swap point
     for different models; this class never does pixel/model work itself).
  3. Storing the result onto the `ProductIndexEntry` (embedding_json /
     embedding_dim / embedding_model).
  4. Avoiding recomputation: if an entry already has an embedding from the
     currently active backend, it's left alone.

Nothing here raises out to callers on the hot search/index path - every
failure (network, decode, backend error) is logged and treated as "no
embedding available yet", never a crash. Callers are responsible for
`db.commit()`; this class only mutates the in-memory entry.
"""

import json
import logging
import math

import requests

from app.config import settings
from app.database import ProductIndexEntry
from app.services.product_index.embedding_backends import EmbeddingBackend, get_backend

logger = logging.getLogger(__name__)

_REQUEST_HEADERS = {"User-Agent": "VisualFindProductIndex/1.0"}

class EmbeddingService:
    """Construct with an explicit `backend` for tests or one-off scripts.
    In normal app code, use the `default_embedding_service` singleton below
    instead of constructing your own - it always resolves the *current*
    `settings.product_index_embedding_backend`, so a config change takes
    effect without restarting anything that cached an instance early.
    """

    def __init__(self, backend: EmbeddingBackend | None = None, timeout: float | None = None):
        self._backend = backend
        self._timeout = timeout

    @property
    def backend(self) -> EmbeddingBackend:
        return self._backend or get_backend()

    @property
    def timeout(self) -> float:
        return self._timeout if self._timeout is not None else settings.product_index_embedding_timeout_seconds

    def needs_embedding(self, entry: ProductIndexEntry) -> bool:
        """The 'avoid recomputing embeddings' rule. An entry does NOT need
        (re-)embedding only if it already has a vector AND that vector came
        from the currently active backend. A missing embedding, or one
        stamped with a different `embedding_model` (e.g. after swapping to
        a new backend), both count as needing one - vectors from different
        models aren't comparable, so a swapped backend must be treated the
        same as "not embedded yet" rather than silently mixing vector
        spaces.
        """
        if not entry.embedding_json:
            return True
        return entry.embedding_model != self.backend.name

    def download_image(self, image_url: str) -> bytes | None:
        try:
            resp = requests.get(image_url, timeout=self.timeout, headers=_REQUEST_HEADERS)
            resp.raise_for_status()
            return resp.content
        except Exception:
            logger.debug("Could not download product image: %s", image_url, exc_info=True)
            return None

    def embed_product(self, entry: ProductIndexEntry, image_url: str | None = None) -> bool:
        """Ensures `entry` has a current embedding.

        Downloads `image_url` (falling back to `entry.image_url`), runs it
        through the active backend, and stores the resulting vector onto
        `entry` in place. Returns True if a *new* embedding was computed
        and stored; False if it was skipped for any reason - already
        embedded by the current backend, no image URL, embeddings disabled,
        or a download/decode/model failure. Callers still need to
        `db.commit()`/`db.add()` as appropriate; this method only mutates
        the passed-in entry.
        """
        image_url = image_url or entry.image_url

        if not settings.product_index_embedding_enabled:
            return False
        if not image_url:
            return False
        if not self.needs_embedding(entry):
            return False

        image_bytes = self.download_image(image_url)
        if image_bytes is None:
            return False

        vector = self._safe_embed(image_bytes, image_url)
        if vector is None:
            return False

        entry.embedding_json = json.dumps(vector)
        entry.embedding_dim = len(vector)
        entry.embedding_model = self.backend.name
        return True

    def _safe_embed(self, image_bytes: bytes, image_url: str) -> list[float] | None:
        try:
            return self.backend.embed(image_bytes)
        except Exception:
            logger.debug("Embedding computation failed for %s (backend=%s)", image_url, self.backend.name, exc_info=True)
            return None

def cosine_similarity(vector_a: list[float], vector_b: list[float]) -> float:
    """Returns a similarity score in roughly [0, 1] for two embeddings of
    the same dimensionality; 0.0 for anything malformed/mismatched (e.g.
    vectors from two different backends) rather than raising."""
    if not vector_a or not vector_b or len(vector_a) != len(vector_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vector_a, vector_b))
    norm_a = math.sqrt(sum(a * a for a in vector_a))
    norm_b = math.sqrt(sum(b * b for b in vector_b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)

# --- PERF: batch cosine similarity against one fixed query vector -----
#
# search_by_image()/find_similar() score one query vector against every
# candidate row in the catalog. Calling cosine_similarity() per-candidate
# recomputes the query vector's own norm on every single call - wasted,
# repeated work that scales with catalog size for no benefit (the query
# vector never changes mid-scan). query_vector_norm() + 
# cosine_similarity_with_query_norm() compute that norm exactly once and
# reuse it for every candidate. Numerically identical to calling
# cosine_similarity() once per pair - this is purely a "don't repeat the
# same computation N times" optimization, not a behavior change.
def query_vector_norm(vector: list[float]) -> float:
    return math.sqrt(sum(v * v for v in vector))

def cosine_similarity_with_query_norm(
    query_vector: list[float], query_norm: float, candidate_vector: list[float]
) -> float:
    """Same result as cosine_similarity(query_vector, candidate_vector),
    but takes the query vector's precomputed norm instead of recomputing
    it - see the module note above."""
    if not query_vector or not candidate_vector or len(query_vector) != len(candidate_vector) or query_norm == 0:
        return 0.0
    dot = sum(a * b for a, b in zip(query_vector, candidate_vector))
    norm_b = math.sqrt(sum(b * b for b in candidate_vector))
    if norm_b == 0:
        return 0.0
    return dot / (query_norm * norm_b)

# The instance the rest of the app should use - always reflects whatever
# backend is currently configured (see EmbeddingService.backend).
default_embedding_service = EmbeddingService()
