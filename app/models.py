"""Pydantic request/response models."""

import re
from enum import Enum
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

class SortBy(str, Enum):
    """Backend-supported sort orders. Frontend can wire these up later."""

    PRICE_LOW = "price_low"
    PRICE_HIGH = "price_high"
    RATING = "rating"
    REVIEWS = "reviews"
    PLATFORM = "platform"

class RankingSignalContribution(BaseModel):
    """One line of a product's ranking explanation - see
    app/services/ranking/ for the engine that produces these. `applied`
    is False (and `raw_score`/`weighted_score` are unused) when this
    signal had nothing to compare for this product - e.g. no rating on
    either side - and was left out of the overall ranking_score entirely,
    rather than being scored as zero."""

    signal: str
    weight: float
    raw_score: Optional[float] = None
    weighted_score: float = 0.0
    applied: bool = True
    explanation: str

class PurchaseLink(BaseModel):
    platform: str
    title: str

    brand: Optional[str] = None

    price: Optional[str] = None
    currency: Optional[str] = None

    link: str
    source_domain: str
    thumbnail: Optional[str] = None

    rating: Optional[float] = None
    review_count: Optional[int] = None

    price_source: Optional[str] = None

    extraction_method: Optional[str] = None

    confidence_score: Optional[float] = None

    is_best_deal: bool = False
    savings: Optional[float] = None

    best_deal_reason: Optional[str] = None

    is_quick_commerce: bool = False
    delivery_estimate: Optional[str] = None

    # Multi-signal ranking (see app/services/ranking/) - populated only for
    # results that went through the Ranking Engine (internal-index
    # matches). None for Google-Lens-sourced results, which aren't ranked
    # by this pipeline.
    ranking_score: Optional[float] = None
    ranking_explanation: Optional[list[RankingSignalContribution]] = None
    ranking_summary: Optional[str] = None

class PriceHistoryComparison(BaseModel):
    """Result of comparing this search's price against the last time the
    same product was searched. See app/services/price_history_service.py."""

    first_time: bool
    message: str

    product_name: Optional[str] = None
    previous_price: Optional[float] = None
    previous_marketplace: Optional[str] = None
    previous_checked_at: Optional[datetime] = None

    current_price: Optional[float] = None
    current_marketplace: Optional[str] = None

    change_percent: Optional[float] = None
    direction: Optional[str] = None

class SearchResponse(BaseModel):
    search_id: int
    best_guess_label: Optional[str] = None
    product_query: Optional[str] = None

    total_matches_found: int
    trusted_matches_returned: int
    priced_count: int = 0

    detected_brand: Optional[str] = None
    brand_confidence: Optional[float] = None
    official_domain: Optional[str] = None
    official_product_found: bool = False

    execution_time_ms: Optional[int] = None
    from_cache: bool = False

    results: list[PurchaseLink]
    note: Optional[str] = None

    is_exact_match: bool = True
    fallback_query: Optional[str] = None

    price_history: Optional[PriceHistoryComparison] = None

    # Which pipeline actually answered this search - "image", "text", or
    # "hybrid" (image + text). Set only by app/services/hybrid_search/;
    # None for calls made directly against the plain image/text pipelines,
    # which predate this field and don't set it.
    search_mode: Optional[str] = None

    # Cheapest priced listing among quick-commerce platforms (Blinkit, Zepto,
    # Instamart, ...) in `results`, if any were found. See
    # app/services/domain_filter.QUICK_COMMERCE_PLATFORMS.
    fastest_delivery: Optional[PurchaseLink] = None

class PriceTrendPoint(BaseModel):
    """One real, previously-recorded price observation for a product - see
    app/services/product_insights_service.py. Never a synthetic point."""

    price: float
    currency: Optional[str] = None
    marketplace: str
    recorded_at: datetime

class ReviewSentiment(BaseModel):
    """A positive/neutral/negative split.

    Two ways this gets built (see app/services/review_sentiment_service.py):
      - Real: actual review text fetched via SerpApi's Google Immersive
        Product API, scored per-review with VADER. `is_estimate=False`,
        `review_count_analyzed` set, and (when available) one real positive
        and one real negative review snippet for transparency.
      - Estimate: no usable review text was found (or too little of it), so
        this falls back to a bucketed guess derived from the average star
        rating (app/services/product_insights_service.py).

    `basis` always says in plain language which of the two this is - the UI
    is never allowed to present an estimate as real analysis.
    """

    positive_pct: int
    neutral_pct: int
    negative_pct: int
    basis: str
    is_estimate: bool = True
    review_count_analyzed: Optional[int] = None
    sample_positive: Optional[str] = None
    sample_negative: Optional[str] = None

class ProductAnalyticsResponse(BaseModel):
    """Powers the Product Analytics page - see app/routers/products.py."""

    product_name: str
    platform: Optional[str] = None
    thumbnail: Optional[str] = None
    current_price: Optional[float] = None
    currency: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None

    price_points: list[PriceTrendPoint] = []
    has_price_trend: bool = False
    price_change_percent: Optional[float] = None
    price_direction: Optional[str] = None

    sentiment: Optional[ReviewSentiment] = None

    summary: list[str] = []
    verdict: str = ""

class HistoryItem(BaseModel):
    id: int
    best_guess_label: Optional[str]
    product_query: Optional[str] = None
    result_count: int
    filtered_count: int
    priced_count: int = 0
    best_deal_platform: Optional[str] = None
    best_deal_price: Optional[float] = None
    detected_brand: Optional[str] = None
    brand_confidence: Optional[float] = None
    official_domain: Optional[str] = None
    execution_time_ms: Optional[int] = None
    created_at: datetime
    thumbnail: Optional[str] = None

    class Config:
        from_attributes = True

class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"

class ChatMessage(BaseModel):
    role: ChatRole
    content: str

class ChatTurnRequest(BaseModel):
    """The client sends the FULL transcript (including the newest user
    message) on every turn - the AI router itself keeps no server-side
    session. See app/services/ai/conversation_manager.py."""

    messages: list[ChatMessage]

class StructuredQuery(BaseModel):
    category: Optional[str] = None
    budget_max: Optional[float] = None
    budget_currency: Optional[str] = "INR"
    brand: Optional[str] = None
    preferences: list[str] = []
    search_text: str

class ChatTurnResponse(BaseModel):
    status: str
    assistant_message: str
    structured_query: Optional[StructuredQuery] = None

class AISearchRequest(BaseModel):
    """Fired once the chat reaches status == 'ready'. `search_text` is
    required; the rest are optional context passed through to the
    recommendation engine's prompt."""

    search_text: str
    category: Optional[str] = None
    budget_max: Optional[float] = None
    budget_currency: Optional[str] = "INR"
    brand: Optional[str] = None
    preferences: list[str] = []

class AIRecommendation(BaseModel):
    product: Optional[PurchaseLink] = None
    reason: Optional[str] = None
    why_it_matches: Optional[str] = None
    money_saved: Optional[float] = None
    is_official_store: bool = False
    alternatives: list[PurchaseLink] = []

    is_exact_match: bool = True
    price_history: Optional[PriceHistoryComparison] = None

class AISearchResponse(BaseModel):
    search: SearchResponse
    recommendation: Optional[AIRecommendation] = None

class TextSearchRequest(BaseModel):
    """Powers the Smart Search Bar's natural-language mode directly (no
    chat round-trip) - e.g. typing "Best moisturizer under 800" and hitting
    search."""

    query: str

class AnalyticsSummary(BaseModel):
    total_searches: int
    most_searched_products: list[dict]
    most_searched_platforms: list[dict]

    most_searched_brands: list[dict]
    average_search_time_ms: Optional[float] = None
    average_products_found: Optional[float] = None
    average_priced_products: Optional[float] = None

    total_products_found: int = 0
    price_hit_rate: Optional[float] = None
    official_match_rate: Optional[float] = None
    fastest_search_ms: Optional[int] = None
    searches_last_7_days: int = 0
    searches_by_day: list[dict] = []
    best_deal_found: Optional[dict] = None
    last_search_at: Optional[str] = None

class SignupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=30)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = Field(default=None, max_length=120)

    @field_validator("username")
    @classmethod
    def _username_format(cls, v: str) -> str:
        v = v.strip()
        if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_.]*", v):
            raise ValueError(
                "Username must start with a letter and contain only letters, numbers, "
                "underscores, or periods."
            )
        return v

    @field_validator("password")
    @classmethod
    def _password_not_all_whitespace(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Password can't be blank")
        return v

class LoginRequest(BaseModel):

    identifier: str = Field(min_length=1, max_length=255)
    password: str

class UsernameAvailabilityResponse(BaseModel):
    username: str
    available: bool

    suggestions: list[str] = []

class UserOut(BaseModel):
    id: int
    username: Optional[str] = None
    email: str
    full_name: Optional[str] = None
    country_code: Optional[str] = None
    country_name: Optional[str] = None
    city: Optional[str] = None
    timezone: str
    created_at: datetime

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)

class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=120)
    country_code: Optional[str] = Field(default=None, max_length=8)
    country_name: Optional[str] = Field(default=None, max_length=120)
    city: Optional[str] = Field(default=None, max_length=120)
    timezone: Optional[str] = Field(default=None, max_length=64)

class ComparePriority(str, Enum):
    """Which axis the user cares about more when two products trade off
    against each other. Feeds the deterministic value-score weighting in
    app/services/ai/compare_engine.py as well as the Gemini prompt."""

    PRICE = "price"
    QUALITY = "quality"

class SmartCompareRequest(BaseModel):
    """Powers the 'Compare Products' feature (two-product AI comparison).

    The two products are exactly what the client already has in hand from
    a real search response - we never re-fetch or re-search for them here.
    Everything else is the short preference questionnaire shown before the
    comparison runs.
    """

    product_a: PurchaseLink
    product_b: PurchaseLink

    budget: Optional[float] = None
    budget_currency: Optional[str] = "INR"
    main_purpose: str
    preferred_brand: Optional[str] = None
    priority: ComparePriority = ComparePriority.QUALITY
    special_preferences: Optional[str] = None

class ProductValueScore(BaseModel):
    """Deterministic 0-100 scores computed from the two REAL products being
    compared (never from the AI) - see compare_engine._compute_value_scores.
    Scores are always relative to the other product in this specific
    comparison, not an absolute scale."""

    price_score: float
    rating_score: float
    reviews_score: float
    overall_value_score: float

class SmartCompareResponse(BaseModel):
    """Result of /api/ai/compare-products. `winner_index` is 0 for
    product_a or 1 for product_b - Gemini (or the deterministic fallback)
    must choose one of the two real products it was given, never a third
    option."""

    winner_index: int
    headline: str
    personalized_reason: str
    price_verdict: str
    quality_verdict: str
    value_verdict: str
    feature_highlights_a: list[str] = []
    feature_highlights_b: list[str] = []
    value_scores_a: ProductValueScore
    value_scores_b: ProductValueScore
    confidence: Optional[float] = None
    used_ai: bool = True

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

class ShoppingStyle(str, Enum):
    """Which axis a person weighs most when browsing results - drives the
    ranking boost in app/services/recommendation_service.py."""

    LOWEST_PRICE = "lowest_price"
    HIGHEST_RATING = "highest_rating"
    BEST_VALUE = "best_value"
    PREMIUM = "premium"

class PreferencesUpdateRequest(BaseModel):
    favorite_categories: list[str] = []
    preferred_platforms: list[str] = []
    budget_min: Optional[float] = Field(default=None, ge=0)
    budget_max: Optional[float] = Field(default=None, ge=0)
    shopping_style: Optional[ShoppingStyle] = None

class PreferencesResponse(BaseModel):
    favorite_categories: list[str] = []
    preferred_platforms: list[str] = []
    budget_min: Optional[float] = None
    budget_max: Optional[float] = None
    shopping_style: Optional[ShoppingStyle] = None
    updated_at: Optional[datetime] = None

class CategoryOption(BaseModel):
    """One selectable category, with the keywords used to match it against
    past searches/products - kept transparent rather than a hidden
    heuristic. See app/services/preferences_service.py::CATEGORY_KEYWORDS."""

    value: str
    label: str

class RecommendationReason(str, Enum):
    SEARCH_HISTORY = "search_history"
    VIEWED = "viewed"
    CATEGORY = "category"
    COMPARED = "compared"
    BUDGET = "budget"

class RecommendationItem(BaseModel):
    reason_type: RecommendationReason
    reason_text: str
    category: Optional[str] = None
    product: PurchaseLink

class RecommendationsResponse(BaseModel):
    items: list[RecommendationItem] = []

    has_enough_signal: bool
    generated_at: datetime

class SavedProductCreateRequest(BaseModel):
    product_name: str = Field(min_length=1, max_length=300)
    platform: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    thumbnail: Optional[str] = None
    link: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None

class SavedProductResponse(BaseModel):
    id: int
    product_name: str
    platform: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    thumbnail: Optional[str] = None
    link: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True

class PriceAlertCreateRequest(BaseModel):
    product_name: str = Field(min_length=1, max_length=300)
    target_price: float = Field(gt=0)
    currency: Optional[str] = "INR"
    platform: Optional[str] = None
    thumbnail: Optional[str] = None
    link: Optional[str] = None

class PriceAlertResponse(BaseModel):
    id: int
    product_name: str
    target_price: float
    currency: Optional[str] = None
    platform: Optional[str] = None
    thumbnail: Optional[str] = None
    link: Optional[str] = None
    is_active: bool
    triggered_at: Optional[datetime] = None
    triggered_price: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True

class NotificationResponse(BaseModel):
    id: int
    alert_id: Optional[int] = None
    type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

class ProductIndexItem(BaseModel):
    """One row of VisualFind's internal Product Index - see
    app/database.py::ProductIndexEntry and
    app/services/product_index/service.py. The raw embedding vector is
    never serialized to the client (large, not human-meaningful); only its
    presence/dimensionality is exposed."""

    id: int
    product_key: str

    title: str
    brand: Optional[str] = None
    category: Optional[str] = None

    image_url: Optional[str] = None
    description: Optional[str] = None

    price: Optional[float] = None
    currency: Optional[str] = None

    rating: Optional[float] = None
    review_count: Optional[int] = None

    source: Optional[str] = None
    product_url: Optional[str] = None

    has_embedding: bool = False
    embedding_dim: Optional[int] = None
    embedding_model: Optional[str] = None

    times_seen: int = 1
    created_at: datetime
    updated_at: Optional[datetime] = None

class ProductIndexListResponse(BaseModel):
    items: list[ProductIndexItem] = []
    total: int
    limit: int
    offset: int

class SimilarProductItem(BaseModel):
    product: ProductIndexItem
    similarity: float

    # Multi-signal ranking (see app/services/ranking/) blending visual
    # similarity with brand/category/price/rating/review_count/user
    # preference/search history/popularity/freshness. `similarity` above
    # stays the plain visual-only cosine score for backwards compatibility;
    # these fields carry the full blended result.
    ranking_score: Optional[float] = None
    ranking_explanation: Optional[list[RankingSignalContribution]] = None
    ranking_summary: Optional[str] = None

class SimilarProductsResponse(BaseModel):
    product_id: int
    items: list[SimilarProductItem] = []

class ProductIndexStatsResponse(BaseModel):
    total_products: int
    products_with_embeddings: int
    by_category: dict[str, int] = {}
    by_source: dict[str, int] = {}

class IndexStatsResponse(BaseModel):
    """Aggregated payload for the Index Statistics dashboard - see
    app/services/index_dashboard_service.py for how each field is computed."""

    # Catalog
    total_products: int
    total_categories: int
    total_brands: int
    by_category: dict[str, int] = {}
    by_brand: dict[str, int] = {}
    by_source: dict[str, int] = {}

    # Embedding generation progress
    products_with_embeddings: int
    embedding_progress_pct: float

    # Index growth
    index_growth_last_24h: int = 0
    index_growth_last_7d: int = 0
    index_growth_by_day: list[dict] = []

    # Duplicate detection (from the Indexing Pipeline's job history)
    total_indexing_jobs: int
    total_products_received: int
    total_duplicates_removed: int
    total_created: int
    total_updated: int
    duplicate_rate_pct: Optional[float] = None

    # Average indexing time (across every completed IndexingJob run,
    # including live-search background indexing)
    average_indexing_time_ms: Optional[float] = None
    indexing_runs_measured: int = 0
    average_indexing_time_by_source: dict[str, float] = {}

    # Search performance / routing
    total_searches: int
    average_search_latency_ms: Optional[float] = None
    cache_hit_searches: int = 0
    cache_hit_rate_pct: Optional[float] = None
    internal_index_searches: int = 0
    internal_index_share_pct: Optional[float] = None
    lens_fallback_searches: int = 0
    lens_fallback_share_pct: Optional[float] = None

    # Popularity
    top_searched_products: list[dict] = []
    top_searched_brands: list[dict] = []

class BackfillEmbeddingsResponse(BaseModel):
    updated: int


class VectorIndexStatsResponse(BaseModel):
    """Introspection into the FAISS-backed nearest-neighbor index (see
    app/services/product_index/vector_index.py) - separate from
    ProductIndexStatsResponse's catalog-level stats since this describes
    the in-memory search structure itself, not the underlying rows."""

    dimensions: list[int] = []
    total_vectors: int = 0
    by_dimension: dict[int, int] = {}


class IndexVersionResponse(BaseModel):
    """One generation of the Product Index's rebuild state - see
    app/database.py::IndexVersion and app/services/indexing/versioning.py."""

    id: int
    version_number: int
    label: Optional[str] = None
    status: str
    embedding_backend: Optional[str] = None
    triggered_by: Optional[str] = None
    notes: Optional[str] = None

    total_entries: int = 0
    embedded_entries: int = 0
    failed_entries: int = 0

    error_message: Optional[str] = None

    created_at: datetime
    activated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class RebuildIndexRequest(BaseModel):
    """Body for POST /api/product-index/index/rebuild."""

    full_reembed: bool = Field(
        default=True,
        description="Recompute every entry's embedding, even if it already has a current one. "
        "Set False for a cheaper 'catch up the stragglers' pass instead of a genuine full rebuild.",
    )
    renormalize: bool = Field(default=True, description="Re-run title/brand/category normalization on every entry.")
    max_embeddings: Optional[int] = Field(default=None, ge=1, le=100000)
    label: Optional[str] = Field(default=None, max_length=120)


class IndexHealthCheckItem(BaseModel):
    name: str
    status: str
    message: str
    details: dict = {}


class IndexHealthResponse(BaseModel):
    status: str
    checked_at: datetime
    issue_count: int
    checks: list[IndexHealthCheckItem]


class IndexHealthHistoryItem(BaseModel):
    id: int
    status: str
    issue_count: int
    checks: list[IndexHealthCheckItem]
    created_at: datetime


class SearchLatencySourceBreakdown(BaseModel):
    count: int
    average_ms: Optional[float] = None
    p95_ms: Optional[float] = None


class SearchLatencyMetricsResponse(BaseModel):
    window_minutes: Optional[int] = None
    sample_size: int
    cache_hits: int
    live_searches: int
    average_latency_ms: Optional[float] = None
    min_latency_ms: Optional[int] = None
    max_latency_ms: Optional[int] = None
    p50_latency_ms: Optional[float] = None
    p95_latency_ms: Optional[float] = None
    p99_latency_ms: Optional[float] = None
    by_query_source: dict[str, SearchLatencySourceBreakdown] = {}


class RawProductIn(BaseModel):
    """One product record for a manual/API batch-indexing request (see
    POST /api/product-index/index/batch). Field names deliberately match
    app.services.indexing.types.RawProduct; a CSV upload goes through the
    same shape internally but is parsed from column-aliased headers
    instead (see app/services/indexing/sources.py) so this schema doesn't
    need to cover every possible supplier header name.
    """

    title: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    source: Optional[str] = None
    product_url: Optional[str] = None
    external_id: Optional[str] = None

class BatchIndexRequest(BaseModel):
    """Body for POST /api/product-index/index/batch - a batch of products
    discovered from any source other than a live Lens search (a partner
    API response the caller already fetched, a manual admin import, ...).
    For pulling directly from a live API URL, use `api_url` instead of
    `products` - the indexing job fetches and parses it server-side."""

    products: list[RawProductIn] = []
    api_url: Optional[str] = Field(
        default=None,
        description="If set (and `products` is empty), the job fetches this URL and expects a JSON array "
        "of product records (or an object with the array under items/products/results/data).",
    )
    source_label: Optional[str] = Field(default=None, max_length=120)

    @field_validator("products")
    @classmethod
    def _cap_batch_size(cls, value: list["RawProductIn"]) -> list["RawProductIn"]:
        if len(value) > 5000:
            raise ValueError("A single batch request supports at most 5000 products; split into multiple requests.")
        return value

class IndexingJobResponse(BaseModel):
    """Status/summary of one batch indexing run - see
    app/database.py::IndexingJob and app/services/indexing/jobs.py."""

    id: int
    source_type: str
    source_label: Optional[str] = None
    status: str

    total_received: int = 0
    invalid: int = 0
    duplicates_removed: int = 0
    created: int = 0
    updated: int = 0
    embedded: int = 0
    failed: int = 0

    error_message: Optional[str] = None

    index_version_id: Optional[int] = None

    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ViewedProductLogRequest(BaseModel):
    """Optional explicit "I looked at this" ping from the frontend (e.g. a
    product card click that doesn't open the full analytics page)."""

    title: str = Field(min_length=1, max_length=300)
    platform: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    thumbnail: Optional[str] = None
    link: Optional[str] = None
