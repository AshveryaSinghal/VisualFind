"""
GoogleLensProvider - the default SearchProvider, wrapping the existing
SerpApi Google Lens integration (app/services/serpapi_client.py) and
Cloudinary image hosting (app/services/cloudinary_service.py) behind the
standard SearchProvider interface (app/services/search_providers/base.py).

This is a pure adapter: none of the underlying Lens/Cloudinary behavior
changed to make this work - upload_image(), google_lens_search(),
extract_candidate_links(), and extract_best_guess() are called exactly as
before, just from here instead of directly from search_service.py.
"""

from __future__ import annotations

import logging

from app.services.cloudinary_service import upload_image
from app.services.search_providers.base import SearchProvider, SearchProviderError
from app.services.search_providers.registry import register_provider
from app.services.search_providers.types import ProviderIdentifyResult
from app.services.serpapi_client import (
    SerpApiError,
    extract_best_guess,
    extract_candidate_links,
    google_lens_search,
)

logger = logging.getLogger(__name__)


class GoogleLensProvider(SearchProvider):
    name = "google_lens"
    display_name = "Google Lens (via SerpApi)"

    def identify(self, image_bytes: bytes, filename: str) -> ProviderIdentifyResult:
        # Image hosting failures are left unwrapped (same behavior as
        # before this module existed) - Cloudinary being unreachable is a
        # different failure mode than "the provider ran and failed" and
        # callers may want to distinguish the two.
        public_image_url = upload_image(image_bytes=image_bytes, filename=filename)
        logger.info("Image uploaded to Cloudinary: %s", public_image_url)

        try:
            lens_response = google_lens_search(public_image_url)
        except SerpApiError as e:
            raise SearchProviderError(f"Google Lens provider: {e}") from e

        candidates = extract_candidate_links(lens_response)
        best_guess = extract_best_guess(lens_response)
        logger.info("Lens Query | best_guess=%s candidates=%d", best_guess, len(candidates))

        return ProviderIdentifyResult(
            candidates=candidates,
            best_guess=best_guess,
            raw_response=lens_response,
            provider_name=self.name,
        )


register_provider(GoogleLensProvider())
