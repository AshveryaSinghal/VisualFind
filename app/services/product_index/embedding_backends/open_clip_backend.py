"""
Optional deep-learning embedding backend: OpenCLIP (`open_clip_torch`).

Unlike `PerceptualHashEmbeddingBackend` (see perceptual_hash.py), this
backend produces embeddings from an actual vision-language model (CLIP),
so visually *and* semantically similar products land close together in
vector space - not just images with similar pixel-level shape/color. That
comes at exactly the cost perceptual_hash.py's docstring called out:
torch + a real model is a heavy dependency and a deploy-shape change.

torch and open_clip_torch are deliberately NOT in the base requirements.txt
(see requirements-openclip.txt) - a multi-hundred-MB dependency isn't
something every deploy target (e.g. Render's free tier) should be forced
to pull in just to import the app. Both are imported lazily, inside
`_ensure_loaded()`, so importing this module - or anything else in the
app - never fails just because they aren't installed. Only *instantiating*
this specific backend (i.e. actually selecting it) does, and with a clear
error message telling you what to install.

To switch to this backend:
  1. pip install -r requirements-openclip.txt
  2. set PRODUCT_INDEX_EMBEDDING_BACKEND=open-clip-vit-b-32 (see .env.example)

Existing perceptual-hash-v1 (or any other prior backend's) embeddings are
automatically treated as stale and recomputed lazily on next access - see
EmbeddingService.needs_embedding - since `name` differs from theirs.
"""

import io
import logging
import threading

from app.config import settings

from .base import EmbeddingBackend

logger = logging.getLogger(__name__)

# Known output dimensionality per OpenCLIP model architecture. Only used as
# a fallback/label; the real source of truth is whatever the loaded model
# actually returns, so a typo'd or unlisted model name doesn't break
# embedding - it just won't be reflected accurately in `dimension` until
# the model has loaded once (see `_ensure_loaded`).
_KNOWN_DIMENSIONS = {
    "ViT-B-32": 512,
    "ViT-B-16": 512,
    "ViT-L-14": 768,
    "ViT-H-14": 1024,
}

class OpenClipEmbeddingBackend(EmbeddingBackend):
    """CLIP image embeddings via the `open_clip_torch` package.

    `name` bakes in the model architecture (e.g. "open-clip-vit-b-32"),
    following the same "vectors from different models aren't comparable"
    convention as perceptual-hash-v1: pointing
    `settings.product_index_openclip_model_name` at a different
    architecture changes `name`, so `EmbeddingService.needs_embedding`
    correctly treats every existing row as stale and re-embeds it, rather
    than silently mixing vector spaces from two different CLIP models.

    The underlying torch model/preprocess pipeline is loaded once per
    (model_name, pretrained) pair and cached at the class level - shared
    across every instance/request in this process - since loading (weight
    download + torch init) takes seconds, while inference takes
    milliseconds. `_model_lock` guards that one-time load against
    concurrent first requests racing each other.
    """

    # Class-level defaults so `OpenClipEmbeddingBackend.name`/`.dimension`
    # are valid even before instantiation (e.g. if something calls
    # `register_backend(OpenClipEmbeddingBackend)`, which reads
    # `backend_cls.name` - see embedding_backends/__init__.py). Overridden
    # per-instance in `__init__` to reflect the *actual* configured model,
    # since that's what every real `get_backend()` call produces.
    name = "open-clip-vit-b-32"
    dimension = 512

    _model_lock = threading.Lock()
    _loaded_key: tuple[str, str] | None = None
    _loaded_model = None
    _loaded_preprocess = None

    def __init__(
        self,
        model_name: str | None = None,
        pretrained: str | None = None,
        device: str | None = None,
    ):
        self._model_name = model_name or settings.product_index_openclip_model_name
        self._pretrained = pretrained or settings.product_index_openclip_pretrained
        self._device = device or settings.product_index_openclip_device

        # e.g. "ViT-B-32" -> "open-clip-vit-b-32"
        self.name = f"open-clip-{self._model_name.lower().replace('/', '-')}"
        self.dimension = _KNOWN_DIMENSIONS.get(self._model_name, 512)

        self._model = None
        self._preprocess = None
        self._torch = None

    def _ensure_loaded(self) -> None:
        """Loads (or reuses an already-loaded) model + preprocessing
        pipeline. Safe to call on every `embed()` - a no-op after the
        first successful call for this (model_name, pretrained) pair."""
        if self._model is not None:
            return

        key = (self._model_name, self._pretrained)
        with self._model_lock:
            if (
                OpenClipEmbeddingBackend._loaded_key == key
                and OpenClipEmbeddingBackend._loaded_model is not None
            ):
                self._model = OpenClipEmbeddingBackend._loaded_model
                self._preprocess = OpenClipEmbeddingBackend._loaded_preprocess
            else:
                try:
                    import open_clip
                    import torch
                except ImportError as exc:
                    raise ImportError(
                        "OpenClipEmbeddingBackend requires the 'torch' and "
                        "'open_clip_torch' packages, which are not part of "
                        "VisualFind's base install (see perceptual_hash.py's "
                        "module docstring for why). Install them with: "
                        "pip install -r requirements-openclip.txt"
                    ) from exc

                model, _, preprocess = open_clip.create_model_and_transforms(
                    self._model_name, pretrained=self._pretrained
                )
                model = model.to(self._device)
                model.eval()

                OpenClipEmbeddingBackend._loaded_model = model
                OpenClipEmbeddingBackend._loaded_preprocess = preprocess
                OpenClipEmbeddingBackend._loaded_key = key
                self._model = model
                self._preprocess = preprocess
                logger.info(
                    "Loaded OpenCLIP model %s (pretrained=%s) on %s",
                    self._model_name,
                    self._pretrained,
                    self._device,
                )

            import torch

            self._torch = torch

    def embed(self, image_bytes: bytes) -> list[float]:
        from PIL import Image

        self._ensure_loaded()
        torch = self._torch

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        tensor = self._preprocess(img).unsqueeze(0).to(self._device)

        with torch.no_grad():
            features = self._model.encode_image(tensor)
            features = features / features.norm(dim=-1, keepdim=True)

        vector = features.squeeze(0).cpu().tolist()
        # Now that the model has actually run, reflect its real output
        # dimensionality rather than the `_KNOWN_DIMENSIONS` guess (only
        # relevant for unlisted/custom model names).
        self.dimension = len(vector)
        return vector
