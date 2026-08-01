"""
Resilient product-query generation.

The Google Shopping price lookup needs a text query, but Google Lens doesn't
reliably give us one clean field to build it from - knowledge_graph is
often absent, visual_matches titles are sometimes noisy web-page titles
rather than product names, etc. So this is a cascade: try the most specific
source first, fall through to the next if it's missing or empty, and only
resort to a generic placeholder if literally nothing usable came back.

This is intentionally decoupled from serpapi_client.py so the fallback
order can change without touching the API wrapper.
"""

from app.services.text_utils import clean_product_title

_MAX_QUERY_LENGTH = 120

def _clean(value: str | None) -> str | None:
    if not value or not isinstance(value, str):
        return None
    value = " ".join(value.split()).strip()
    if not value:
        return None

    return clean_product_title(value)

def build_product_query(lens_response: dict, candidates: list[dict]) -> tuple[str, str]:
    """
    Returns (query, source) where source documents which strategy won, e.g.
    for the "Shopping Query Source" log line and for search history.
    """
    strategies: list[tuple[str, str | None]] = [
        (
            "knowledge_graph_title",
            _clean(lens_response.get("knowledge_graph", {}).get("title")),
        ),
        (
            "search_query_displayed",
            _clean(lens_response.get("search_information", {}).get("query_displayed")),
        ),
        (
            "top_product_title",
            _clean(candidates[0]["title"]) if candidates else None,
        ),
        (
            "first_visual_match_title",
            _clean(next((c["title"] for c in candidates if c.get("bucket") == "visual_matches"), None)),
        ),
    ]

    for source_name, value in strategies:
        if value:
            return value[:_MAX_QUERY_LENGTH], source_name

    return "product", "fallback_generic"
