"""
Search Provider abstraction.

  * base.py     - the SearchProvider interface + SearchProviderError.
  * types.py    - ProviderIdentifyResult, the standardized return shape.
  * registry.py - register_provider()/get_provider(), keyed on
                  settings.search_provider.
  * google_lens.py - the default (and, today, only) built-in provider: a
                  thin adapter over the existing SerpApi Google Lens +
                  Cloudinary integration.

Importing this package guarantees every built-in provider has registered
itself (see the import at the bottom of this file) before anything calls
get_provider(). Adding a future built-in provider (Bing Visual Search, a
retailer API, ...) is one more class + one more import line here - see
base.py's module docstring for the full three-step recipe.
"""

from app.services.search_providers.base import SearchProvider, SearchProviderError
from app.services.search_providers.registry import (
    get_provider,
    list_providers,
    register_provider,
    unregister_provider,
)
from app.services.search_providers.types import ProviderIdentifyResult

# Triggers self-registration - see the bottom of google_lens.py.
from app.services.search_providers import google_lens  # noqa: F401,E402

__all__ = [
    "SearchProvider",
    "SearchProviderError",
    "ProviderIdentifyResult",
    "get_provider",
    "register_provider",
    "unregister_provider",
    "list_providers",
]
