"""
The Search Provider abstraction.

Every "given an uploaded product photo, find candidate purchase links"
integration - Google Lens today; Bing Visual Search, a retailer's own
visual-search API, or anything else tomorrow - implements this one
interface. app/services/search_service.py (the search pipeline) only ever
talks to a provider through this contract: it doesn't import
serpapi_client.py, cloudinary_service.py, or any other provider-specific
module directly, and doesn't know or care which concrete provider answered
the call.

Adding a new provider is exactly three steps, none of which touch the
pipeline:

  1. Write a class implementing SearchProvider (see
     app/services/search_providers/google_lens.py for a complete,
     working example - it's a thin adapter over the existing SerpApi +
     Cloudinary integration, nothing about Lens/Cloudinary changed to
     make this work).
  2. Call register_provider(YourProvider()) once, at import time (see the
     bottom of google_lens.py), and add that import to
     search_providers/__init__.py so it runs on startup.
  3. Point settings.search_provider at its `name` (or pass
     get_provider("your_provider_name") explicitly for a one-off call).

No change to search_service.py, hybrid_search/service.py, or any router is
ever required to add, remove, or switch providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.services.search_providers.types import ProviderIdentifyResult


class SearchProviderError(Exception):
    """The one exception type every SearchProvider is expected to raise on
    failure - network error, auth failure, quota exceeded, a malformed
    response, whatever provider-specific exception it hit internally, it
    wraps it in this before it escapes identify(). That's what lets
    app/routers/search.py return a consistent 502 for "the visual search
    backend failed" without needing to know or care which provider is
    currently active.
    """


class SearchProvider(ABC):
    """Stateless is the expectation (same convention as
    IndexingPipeline/default_pipeline) - a single instance is registered
    once and reused across every request."""

    #: Short, stable, machine-readable identifier - what
    #: settings.search_provider is set to, and what the registry keys on.
    #: Never change this for an already-deployed provider: anyone who's
    #: pinned settings.search_provider to it would silently point nowhere.
    name: str = ""

    #: Human-readable label, safe to show in logs/admin UIs.
    display_name: str = ""

    @abstractmethod
    def identify(self, image_bytes: bytes, filename: str) -> ProviderIdentifyResult:
        """Identify candidate purchase links for an uploaded product
        photo.

        Must raise SearchProviderError (not a provider-specific exception
        type) on any failure - network error, auth failure, quota
        exceeded, unparseable response, etc. - so every caller can handle
        every provider's failures identically. A provider that
        legitimately just found nothing should return an empty
        ProviderIdentifyResult([], best_guess=None), not raise.
        """
        raise NotImplementedError
