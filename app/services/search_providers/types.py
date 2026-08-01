"""
Standardized data shapes exchanged between the search pipeline
(app/services/search_service.py) and any SearchProvider implementation
(app/services/search_providers/). Keeping these separate from
serpapi_client.py's SerpApi-shaped dicts is what lets a second provider
(Bing Visual Search, a retailer's own visual-search API, ...) slot in
without either module needing to change.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProviderIdentifyResult:
    """What every SearchProvider.identify() call returns, regardless of
    which external API produced it.

    candidates: a list of dicts shaped exactly like the ones
        app/services/serpapi_client.py::extract_candidate_links has always
        produced - {"title", "link", "price", "currency", "thumbnail",
        "bucket"} - since every downstream consumer (domain_filter,
        price_service, dedupe, query_builder, brand_resolution) already
        expects that shape. A provider with richer per-candidate data
        (rating, review_count, ...) may include extra keys too; consumers
        that don't know about them simply ignore them, same as an
        unrecognized SerpApi field would be today.

    best_guess: the provider's single best label for "what product is
        this", or None if it couldn't produce one.

    raw_response: the provider's own raw payload, kept around *opaquely*
        for the handful of consumers that can make extra use of it if it
        happens to contain the keys they're hoping for - query_builder's
        knowledge_graph/search_information cascade, brand_resolution's
        detector. Providers with nothing like that just return {}: every
        consumer of this field already degrades gracefully to
        candidate-based heuristics when those keys are missing, since
        that already happens whenever SerpApi's own response omits them
        (see text_search_service.py, which has always passed
        lens_response={} for text-only searches).

    provider_name: which provider produced this result. Stamped onto
        SearchLog / indexing records is a natural future use; kept here
        so callers don't have to separately track "which provider did I
        just call".
    """

    candidates: list[dict]
    best_guess: str | None = None
    raw_response: dict = field(default_factory=dict)
    provider_name: str = ""
