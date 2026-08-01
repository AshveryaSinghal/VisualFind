"""
Provider registry: where SearchProvider implementations register
themselves, and where the search pipeline looks one up by name.

See app/services/search_providers/base.py for the interface itself and
app/services/search_providers/google_lens.py for a complete example
implementation + registration.
"""

from __future__ import annotations

from app.config import settings
from app.services.search_providers.base import SearchProvider, SearchProviderError

_PROVIDERS: dict[str, SearchProvider] = {}


def register_provider(provider: SearchProvider) -> None:
    """Adds (or replaces) a provider in the registry, keyed on its
    `.name`. Safe to call more than once for the same name (e.g. test
    setup re-registering a stand-in) - the later registration just wins.
    """
    if not provider.name:
        raise ValueError(f"{provider.__class__.__name__} must set a non-empty `name`")
    _PROVIDERS[provider.name] = provider


def unregister_provider(name: str) -> None:
    """Mainly for tests that register a throwaway provider and want to
    clean up afterwards - not something normal app code needs to call."""
    _PROVIDERS.pop(name, None)


def list_providers() -> list[str]:
    return sorted(_PROVIDERS)


def get_provider(name: str | None = None) -> SearchProvider:
    """Returns the provider to use for this call: the explicitly
    requested `name`, or settings.search_provider if omitted. This is the
    *only* place in the app that decides which provider answers a search,
    so switching providers app-wide is always a one-line settings change,
    and nothing upstream of this function needs to know that happened.
    """
    key = name or settings.search_provider
    try:
        return _PROVIDERS[key]
    except KeyError:
        raise SearchProviderError(
            f"Unknown search provider '{key}'. Registered providers: "
            f"{list_providers() or '(none registered)'}"
        ) from None
