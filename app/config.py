"""
Central application settings, loaded from environment variables / .env.

Every tunable used anywhere in the codebase should live here, not as a
hardcoded literal buried in a service module. That keeps "make this
configurable" a one-line change instead of a grep-and-replace.
"""

import json

from pydantic_settings import BaseSettings

class Settings(BaseSettings):

    serpapi_key: str
    serpapi_country: str = "in"
    serpapi_language: str = "en"

    database_url: str = "sqlite:///./visualfind.db"

    max_upload_mb: int = 8

    cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    rate_limit_per_minute: int = 20

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allowed_origins.split(",") if origin.strip()]

    cloudinary_cloud_name: str
    cloudinary_api_key: str
    cloudinary_api_secret: str

    cache_ttl_seconds: int = 1800

    enable_page_metadata_fallback: bool = True
    page_metadata_fetch_timeout_seconds: float = 5.0

    enable_headless_browser_fallback: bool = True
    headless_browser_timeout_seconds: float = 12.0

    enable_brand_resolution: bool = True

    min_brand_confidence_for_domain_resolution: float = 0.4

    enable_brand_page_metadata_lookup: bool = True

    brand_search_timeout_seconds: float = 6.0

    # --- Price extraction concurrency ---
    # enrich_with_live_prices() (app/services/price_service.py) resolves a
    # live price for every trusted candidate on the hot search path. Each
    # candidate's extraction is an independent, blocking network call (and,
    # for the headless-browser fallback tier, a full page render) - none of
    # them share state, so they're safe to run concurrently instead of
    # strictly one after another. This bounds how many run at once; same
    # "thread pool for independent blocking I/O" pattern as
    # indexing_embedding_workers above. 1 reproduces the old fully
    # sequential behavior exactly, for anyone who wants to disable this.
    price_extraction_workers: int = 6

    gemini_api_key: str = ""

    gemini_model: str = "gemini-flash-latest"
    gemini_timeout_seconds: float = 30.0

    gemini_chat_cache_ttl_seconds: int = 60

    ai_max_conversation_turns: int = 20

    jwt_secret_key: str = "dev-only-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7

    password_reset_token_expire_minutes: int = 30

    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_from_email: str = "no-reply@visualfind.app"
    smtp_from_name: str = "VisualFind"

    frontend_base_url: str = "http://localhost:5173"

    # Internal Product Index (see app/services/product_index/service.py).
    # Turned OFF: its image matching (a perceptual hash + color histogram,
    # not a real vision model) can't reliably tell visually-similar but
    # different products apart - e.g. two brands' lip balms shot the same
    # generic way (centered tube, white background) scored as a near-exact
    # match and returned the wrong brand's result. Every image search now
    # always goes through the Google Lens pipeline instead, which doesn't
    # have that failure mode. Left in place (not deleted) rather than
    # ripped out, since hybrid_search's image+text mode also reads this
    # flag and already degrades gracefully to Lens+text re-rank when it's
    # off - see hybrid_search/service.py::_run_hybrid.
    enable_product_index: bool = False

    # Whether the Embedding Service (app/services/product_index/embedding_service.py)
    # runs at all. Turning this off still populates the catalog
    # (title/brand/price/...), just without embedding_json ever being filled in.
    product_index_embedding_enabled: bool = True

    # Which EmbeddingBackend to use (see
    # app/services/product_index/embedding_backends/). Swapping models is
    # meant to be exactly this: change this string to a registered
    # backend's `name`, no code changes required.
    product_index_embedding_backend: str = "perceptual-hash-v1"

    # Per-image timeout for the embedding download+compute.
    product_index_embedding_timeout_seconds: float = 4.0

    # Only read/used when product_index_embedding_backend is an OpenCLIP
    # backend name (see embedding_backends/open_clip_backend.py). torch +
    # open_clip_torch are an optional heavy dependency (requirements-openclip.txt),
    # not part of the base install - see that file's module docstring.
    product_index_openclip_model_name: str = "ViT-B-32"
    product_index_openclip_pretrained: str = "openai"
    product_index_openclip_device: str = "cpu"

    # Upper bound on how many *new* embeddings a single search can trigger
    # (each is a network fetch of a product thumbnail). Every new product
    # is embedded inline by default - this cap is only a latency safety
    # valve for an unusually large batch of brand-new products in one
    # search, not something you need to raise for normal traffic. Products
    # already embedded from an earlier search are skipped instantly by
    # EmbeddingService.needs_embedding and never count against this cap.
    # Anything the cap does skip is still cataloged and gets picked up by
    # a later call to backfill_embeddings().
    product_index_max_embeddings_per_search: int = 25

    # Whether every image upload also checks VisualFind's own Product
    # Index. Google Lens/SerpApi is the primary, trusted source of truth
    # for every live search - see app/services/search_service.py::
    # process_image_search - and always runs. When this flag is on, the
    # internal index is queried *in addition* to Lens, purely to surface
    # a handful of supplementary "also in our catalog" recommendations
    # appended after Lens's own results; it never answers a search on its
    # own or replaces/short-circuits the Lens call, since the catalog's
    # source/price data isn't reliable enough to stand alone (see
    # app/services/product_index/service.py::search_by_image).
    #
    # Off by default alongside enable_product_index above - see that
    # flag's comment for why (unreliable brand/product matching).
    enable_internal_index_search: bool = False

    # How many catalog rows a single image search compares itself against
    # (top-N by cosine similarity, before the similarity floor is applied).
    product_index_search_top_k: int = 10

    # Minimum cosine similarity for a catalog row to count as a real match
    # at all. Anything below this is discarded rather than returned as a
    # low-confidence "match".
    #
    # Deliberately strict (not the more typical 0.7-0.85 you'd use for a
    # real semantic embedding): the default backend is a perceptual
    # hash + color histogram, not a deep-learning model, so it can only
    # reliably recognize near-duplicate *photos* (the same product
    # searched again, or the same stock photo reused). It has no notion of
    # brand/logo/text, so two different products shot the same generic way
    # (centered on white, similar lighting) can otherwise still look
    # deceptively close - this floor keeps the internal index to "very
    # confident it's the same photo" rather than "generally similar-looking
    # item", trading recall for not returning the wrong product.
    product_index_search_min_similarity: float = 0.96

    # No longer a "skip Google Lens" threshold - Lens always runs first,
    # see enable_internal_index_search above. Kept as the minimum number
    # of qualifying internal-index matches (see
    # product_index_search_min_similarity) required before any
    # supplemental catalog recommendations are considered worth adding at
    # all, for a bare image search.
    product_index_search_min_matches: int = 3

    # Upper bound on how many internal-index matches get appended as
    # supplemental "also in our catalog" recommendations after Google
    # Lens's own (primary, trusted) results, for a bare image search - see
    # app/services/search_service.py::process_image_search. Keeps the
    # index from ever dominating the response even when it has plenty of
    # matches.
    internal_index_max_supplemental_results: int = 5

    # --- Product Vector Index (see app/services/product_index/vector_index.py) ---
    # Where the on-disk FAISS index files (one per embedding dimension)
    # and their manifest are persisted, so the index survives a restart
    # without needing to re-embed every row again. Relative paths resolve
    # against the process's working directory (same convention as
    # `database_url=sqlite:///./visualfind.db`).
    product_index_faiss_dir: str = "data/faiss_index"

    # Whether the FAISS index is loaded from `product_index_faiss_dir` at
    # startup and saved back to it on shutdown / after index-changing
    # admin operations (rebuild, batch indexing). Turning this off keeps
    # the index in memory only - it's still fully rebuilt by reconciling
    # against the database the first time anything searches it (see
    # ProductVectorIndexRegistry.reconcile), it just doesn't survive a
    # restart. Useful for tests/CI, where a stray index file left on disk
    # would otherwise be an unwanted source of cross-run state.
    product_index_faiss_persist_enabled: bool = True

    # --- Ranking Engine (see app/services/ranking/) ---
    # Master on/off switch for multi-signal ranking of internal-index
    # search results. When False, ranking falls back to visual_similarity
    # alone (pure cosine order) - see product_index_service.rank_matches
    # and .rank_similar.
    enable_ranking_engine: bool = True

    # Per-signal weight overrides as a JSON object, e.g.
    # '{"visual_similarity": 4.0, "freshness": 0.1}'. Any signal not
    # mentioned keeps its RankingSignal.default_weight (see
    # app/services/ranking/registry.py::default_weights). Invalid or blank
    # JSON is treated as "no overrides" rather than raising - see the
    # ranking_weight_overrides property below.
    ranking_weights_json: str = "{}"

    @property
    def ranking_weight_overrides(self) -> dict[str, float]:
        try:
            data = json.loads(self.ranking_weights_json)
        except (json.JSONDecodeError, TypeError):
            return {}
        if not isinstance(data, dict):
            return {}
        overrides: dict[str, float] = {}
        for key, value in data.items():
            try:
                overrides[str(key)] = float(value)
            except (TypeError, ValueError):
                continue
        return overrides

    # How many catalog rows the multi-signal re-ranker pulls into its
    # candidate pool for a product-to-product "similar products" lookup,
    # relative to the requested top_k (pool_size = top_k * this multiplier,
    # floored at 20) - see product_index_service.rank_similar. A larger
    # pool gives the non-visual signals (brand, price, rating, ...) real
    # room to reorder results instead of just re-sorting an
    # already-visual-only top_k.
    ranking_similar_pool_multiplier: int = 4

    # --- Indexing Pipeline (see app/services/indexing/) ---
    # How many worker threads the pipeline uses to compute embeddings
    # concurrently within one run (each is a blocking network image
    # download + backend.embed() call) - this is what "asynchronous where
    # appropriate" means for indexing: DB writes stay sequential/safe on
    # one session, but the slow, independent network+CPU work per product
    # is parallelized across threads instead of looping one at a time.
    indexing_embedding_workers: int = 8

    # Safety cap on how many *new* embeddings a single batch (CSV/API)
    # indexing run will attempt inline, separate from
    # product_index_max_embeddings_per_search (which caps a single live
    # search). A batch job that exceeds this just leaves the remaining
    # rows uncatalogued-without-an-embedding, to be picked up by the
    # existing backfill_embeddings() job.
    indexing_batch_max_embeddings: int = 500

    # --- Hybrid Search (see app/services/hybrid_search/) ---
    # Master on/off switch for the combined image+text search endpoint
    # (POST /api/search/hybrid). Existing /api/search/image and
    # /api/ai/text-search endpoints are untouched either way.
    enable_hybrid_search: bool = True

    # No longer used to decide whether the catalog can answer a hybrid
    # search on its own - Google Lens is always the primary source there
    # too (see app/services/hybrid_search/service.py, which now just
    # delegates to search_service.process_image_search and re-ranks
    # whatever comes back - Lens results plus any supplemental internal-
    # index recommendations - by text relevance/budget). Kept only so
    # existing deployments overriding it don't hit an unknown-setting
    # error; has no effect.
    hybrid_search_min_internal_matches: int = 1

    # --- Search Provider abstraction (see app/services/search_providers/) ---
    # Which registered SearchProvider answers "identify candidate purchase
    # links for this photo" whenever the internal Product Index doesn't
    # have enough matches on its own (see product_index_search_min_matches
    # / hybrid_search_min_internal_matches above). "google_lens" is the
    # only built-in provider today; adding a new one (Bing Visual Search,
    # a retailer's own visual-search API, ...) and pointing this at its
    # registered `name` is the entire integration - no changes to
    # search_service.py, hybrid_search/service.py, or any router required.
    search_provider: str = "google_lens"

    # --- Review Sentiment (see app/services/review_sentiment_service.py) ---
    # Master on/off switch for fetching real per-review text (via SerpApi's
    # Google Immersive Product API) and running actual text-based sentiment
    # analysis on it. When False (or when no reviews can be found for a
    # product), falls back to the old rating-bucket estimate in
    # app/services/product_insights_service.py - never fabricated either way.
    enable_real_review_sentiment: bool = True

    # Upper bound on how many individual review texts are pulled + scored
    # per product. SerpApi's Immersive Product API returns a first page of
    # reviews per call; this just caps how many of those we bother scoring.
    review_sentiment_max_reviews: int = 25

    # If fewer than this many real review texts are found, real analysis is
    # considered too thin to trust over the rating-bucket estimate - falls
    # back rather than reporting a 100%/0% split off two reviews.
    review_sentiment_min_reviews: int = 3

    # Separate (longer) cache TTL from the general shopping-query cache -
    # review text for a given product changes far less often than price, so
    # there's no reason to pay for a fresh SerpApi call as frequently.
    review_sentiment_cache_ttl_seconds: int = 21600

    class Config:
        env_file = ".env"

settings = Settings()
