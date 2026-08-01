"""
Default embedding backend: a lightweight perceptual embedding computed
from actual pixel content (average-hash + coarse color histogram) - NOT a
placeholder of zeros or random noise. Visually similar product photos land
close together in this vector space.

This is intentionally NOT a deep-learning embedding (no CLIP/ResNet/ViT).
Pulling in torch/transformers is a heavy dependency and deploy-shape
change; Pillow is a small, already-installed one. When a real vision model
is wanted, add a new `EmbeddingBackend` implementation (see base.py) and
point `settings.product_index_embedding_backend` at its `name` - this
class doesn't need to change, and nothing outside embedding_backends/ does
either.

v2 fix - unit-normalize each sub-vector before concatenating
--------------------------------------------------------------
v1 concatenated the raw 64-dim hash vector (entries 0.0/1.0, L2 norm
~4-6) with the raw 64-dim histogram vector (entries are pixel fractions
that sum to 1 across the whole vector, so its L2 norm is typically well
under 1). Cosine similarity is computed over the *whole* concatenated
vector, so the sub-vector with the larger norm dominates the score almost
entirely - in practice that meant color was contributing almost nothing,
and the match was really just "does this image have the same coarse
light/dark layout", which is true of most product photos shot the same
way (centered item, white background, similar lighting) regardless of
brand. That's what let two different lip balms match as "the same
product" above the similarity floor.

Normalizing each sub-vector to unit L2 norm *before* concatenation makes
shape and color each contribute proportionally (~50/50) to the final
cosine similarity, so packaging color/label actually counts instead of
being drowned out. `name` is bumped to force existing catalog rows (all
embedded under the old, unbalanced vectors) to be re-embedded rather than
silently compared against the new balanced vectors - see
EmbeddingService.needs_embedding.
"""

import io
import math

from PIL import Image

from .base import EmbeddingBackend

class PerceptualHashEmbeddingBackend(EmbeddingBackend):
    # Bumped from "perceptual-hash-v1" so every existing catalog row gets
    # re-embedded with the balanced vectors below instead of being treated
    # as already up to date (see EmbeddingService.needs_embedding).
    name = "perceptual-hash-v2"

    _HASH_SIZE = 8  # 8x8 average-hash -> 64 dims
    _HIST_BINS = 4  # 4x4x4 color histogram -> 64 dims
    dimension = _HASH_SIZE * _HASH_SIZE + _HIST_BINS**3

    def embed(self, image_bytes: bytes) -> list[float]:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        hash_vec = self._normalize(self._average_hash_vector(img))
        color_vec = self._normalize(self._color_histogram_vector(img))
        return hash_vec + color_vec

    @staticmethod
    def _normalize(vector: list[float]) -> list[float]:
        """Unit-L2-normalizes a sub-vector so it contributes proportionally
        once concatenated with the other sub-vector, rather than whichever
        one happens to have the larger raw magnitude dominating cosine
        similarity. A near-zero vector (e.g. a flat/blank image) is left
        as-is rather than dividing by ~0."""
        norm = math.sqrt(sum(v * v for v in vector))
        if norm < 1e-9:
            return vector
        return [v / norm for v in vector]

    def _average_hash_vector(self, img: "Image.Image") -> list[float]:
        """Coarse shape/luminance layout: shrink to a tiny grayscale grid
        and threshold each pixel against the grid's mean brightness."""
        small = img.convert("L").resize((self._HASH_SIZE, self._HASH_SIZE))
        pixels = list(small.getdata())
        mean = sum(pixels) / len(pixels)
        return [1.0 if p >= mean else 0.0 for p in pixels]

    def _color_histogram_vector(self, img: "Image.Image") -> list[float]:
        """Coarse color palette: what fraction of pixels fall in each of
        4x4x4 = 64 RGB buckets."""
        small = img.resize((64, 64))
        pixels = list(small.getdata())
        bins = [0] * (self._HIST_BINS**3)
        step = 256 // self._HIST_BINS
        for r, g, b in pixels:
            ri = min(r // step, self._HIST_BINS - 1)
            gi = min(g // step, self._HIST_BINS - 1)
            bi = min(b // step, self._HIST_BINS - 1)
            bins[(ri * self._HIST_BINS + gi) * self._HIST_BINS + bi] += 1
        total = float(len(pixels)) or 1.0
        return [count / total for count in bins]
