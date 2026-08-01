"""
Thin wrapper around two SerpApi engines:

  - google_lens     -> identifies the product from the uploaded photo and
                        surfaces candidate purchase links (visual_matches,
                        products, exact_matches).
  - google_shopping  -> given a text query, returns live shopping listings
                        with real extracted prices, ratings and review
                        counts. This is the actual live-price source (see
                        app/services/price_service.py) - we never scrape the
                        trusted retailers directly for this tier, since
                        Amazon/Flipkart/Myntra/Nykaa all prohibit it in their
                        ToS and actively fight it with bot detection (see
                        README). Google Shopping already licenses this data
                        from the retailers, so it's the defensible source.

  - google_immersive_product -> given the immersive_product_page_token a
                        google_shopping result carries, returns the full
                        "product popup" - including actual user_reviews
                        (real review title/text/rating, not just an
                        aggregate). This is what feeds real, per-review-text
                        sentiment analysis (see
                        app/services/review_sentiment_service.py) instead of
                        the old rating-bucket estimate. Same licensing
                        rationale as google_shopping above - this is Google's
                        own aggregation of review data, not us scraping the
                        retailer directly.

Docs: https://serpapi.com/google-lens-api, https://serpapi.com/google-shopping-api,
      https://serpapi.com/google-immersive-product-api

IMPORTANT: google_lens takes an image URL, not raw bytes. The caller is
responsible for making the uploaded image reachable at a public URL first
(see app/services/cloudinary_service.py).
"""

import logging

import requests

from app.config import settings

logger = logging.getLogger(__name__)

SERPAPI_ENDPOINT = "https://serpapi.com/search"
REQUEST_TIMEOUT_SECONDS = 20

class SerpApiError(Exception):
    pass

def _call_serpapi(params: dict) -> dict:
    """Shared request/error-handling path for both engines."""
    try:
        resp = requests.get(SERPAPI_ENDPOINT, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException as e:
        raise SerpApiError(f"Network error calling SerpApi: {e}") from e

    if resp.status_code == 401:
        raise SerpApiError("SerpApi rejected the API key. Check SERPAPI_KEY in .env.")
    if resp.status_code == 429:
        raise SerpApiError("SerpApi monthly free-tier quota exceeded.")
    if resp.status_code != 200:
        raise SerpApiError(f"SerpApi returned HTTP {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    if "error" in data:
        raise SerpApiError(f"SerpApi error: {data['error']}")

    return data

def google_lens_search(image_url: str) -> dict:
    """
    Calls SerpApi's Google Lens engine with type=all so we get products,
    exact_matches, and visual_matches in one call (one call = one quota unit,
    so don't split this into multiple type-specific calls).
    """
    params = {
        "engine": "google_lens",
        "url": image_url,
        "type": "all",
        "api_key": settings.serpapi_key,
    }
    return _call_serpapi(params)

_LENS_BUCKETS_IN_PRIORITY_ORDER = ("products", "exact_matches", "visual_matches")

def extract_candidate_links(serpapi_response: dict) -> list[dict]:
    """
    Normalizes the different result buckets SerpApi returns (not all are
    always present) into one flat list of
    {title, link, price, currency, thumbnail, bucket} dicts, ordered by
    bucket priority so the most shopping-relevant candidates come first.
    """
    candidates: list[dict] = []

    for bucket_key in _LENS_BUCKETS_IN_PRIORITY_ORDER:
        for item in serpapi_response.get(bucket_key, []) or []:
            link = item.get("link")
            if not link:
                continue

            price_info = item.get("price") or {}
            candidates.append(
                {
                    "title": item.get("title", "Unknown product"),
                    "link": link,
                    "price": price_info.get("value") if isinstance(price_info, dict) else None,
                    "currency": price_info.get("currency") if isinstance(price_info, dict) else None,
                    "thumbnail": item.get("thumbnail"),
                    "bucket": bucket_key,
                }
            )

    return candidates

def extract_best_guess(serpapi_response: dict) -> str | None:
    """
    Cascading fallback so we very rarely surface no label at all:
    knowledge graph title -> displayed search query -> first candidate title.
    """
    knowledge_graph_title = serpapi_response.get("knowledge_graph", {}).get("title")
    if knowledge_graph_title:
        return knowledge_graph_title

    query_displayed = serpapi_response.get("search_information", {}).get("query_displayed")
    if query_displayed:
        return query_displayed

    for bucket_key in _LENS_BUCKETS_IN_PRIORITY_ORDER:
        items = serpapi_response.get(bucket_key) or []
        if items and items[0].get("title"):
            return items[0]["title"]

    return None

def google_shopping_search(query: str) -> dict:
    """Live shopping listings (price, rating, reviews, retailer) for a text query."""
    params = {
        "engine": "google_shopping",
        "q": query,
        "gl": settings.serpapi_country,
        "hl": settings.serpapi_language,
        "api_key": settings.serpapi_key,
    }
    return _call_serpapi(params)

def google_immersive_product(page_token: str) -> dict:
    """
    Calls SerpApi's Google Immersive Product engine with the page_token
    carried by a google_shopping result (`immersive_product_page_token`
    field - see extract_shopping_offers below). Returns the full product
    popup: stores, about_the_product, ratings breakdown, and - the part we
    actually want here - `user_reviews`, real individual reviews with
    title/text/rating/date. Costs one SerpApi search unit, same as any
    other engine call, so callers should cache the result (see
    review_sentiment_service.py) rather than calling this on every page load.
    """
    params = {
        "engine": "google_immersive_product",
        "page_token": page_token,
        "api_key": settings.serpapi_key,
    }
    return _call_serpapi(params)

def extract_user_reviews(immersive_product_response: dict) -> list[dict]:
    """
    Normalizes product_results.user_reviews into
    {title, text, rating, date, source, user_name} dicts. Every field read
    defensively - SerpApi's exact field set varies by product/retailer, and
    a review with no `text` at all is dropped since there's nothing to
    analyze for sentiment.
    """
    product_results = immersive_product_response.get("product_results") or {}
    raw_reviews = product_results.get("user_reviews") or []

    reviews: list[dict] = []
    for item in raw_reviews:
        text = (item.get("text") or "").strip()
        if not text:
            continue
        reviews.append(
            {
                "title": item.get("title"),
                "text": text,
                "rating": item.get("rating"),
                "date": item.get("date"),
                "source": item.get("source"),
                "user_name": item.get("user_name"),
            }
        )
    return reviews

def google_web_search(query: str) -> dict:
    """
    Plain Google web search (engine=google). Used by the Brand Resolution
    engine (app/services/brand_resolution/) for two purposes:
      - finding a brand's official website when it's not in the local
        brand-domain map (e.g. `"<brand> official website"`)
      - locating a specific product page on an already-resolved official
        domain (e.g. `"site:<domain> <product query>"`)
    Kept in this module rather than brand_resolution/ so there's exactly one
    place that owns talking to SerpApi, matching the rest of this client.
    """
    params = {
        "engine": "google",
        "q": query,
        "gl": settings.serpapi_country,
        "hl": settings.serpapi_language,
        "api_key": settings.serpapi_key,
    }
    return _call_serpapi(params)

def extract_organic_results(search_response: dict) -> list[dict]:
    """Normalizes organic_results into {title, link, snippet, displayed_link} dicts."""
    results: list[dict] = []
    for item in search_response.get("organic_results", []) or []:
        link = item.get("link")
        if not link:
            continue
        results.append(
            {
                "title": item.get("title"),
                "link": link,
                "snippet": item.get("snippet"),
                "displayed_link": item.get("displayed_link"),
            }
        )
    return results

def extract_shopping_offers(shopping_response: dict) -> list[dict]:
    """
    Normalizes shopping_results into {title, link, price, currency, rating,
    reviews, thumbnail, source, page_token} dicts. Every field is read
    defensively since SerpApi's exact field set for a given listing varies
    by retailer.

    `page_token` (from `immersive_product_page_token`, when present) is what
    lets review_sentiment_service.py fetch this specific listing's real
    review text via google_immersive_product() above - not every shopping
    result has one (depends on whether Google has an immersive popup for
    that product).
    """
    offers: list[dict] = []

    for item in shopping_response.get("shopping_results", []) or []:
        link = item.get("product_link") or item.get("link")
        if not link:
            continue

        price = item.get("extracted_price")
        if price is None:
            price = item.get("price")

        offers.append(
            {
                "title": item.get("title", "Unknown product"),
                "link": link,
                "price": price,
                "currency": item.get("currency"),
                "rating": item.get("rating"),
                "reviews": item.get("reviews"),
                "thumbnail": item.get("thumbnail"),
                "source": item.get("source"),
                "page_token": item.get("immersive_product_page_token"),
            }
        )

    return offers
