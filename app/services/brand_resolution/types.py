"""
Shared data shapes for the Brand Resolution engine.

Mirrors the style of app/services/price_extraction/types.py: plain
dataclasses, internal-only, never cross the HTTP boundary directly (the
orchestrator translates OfficialProduct into the same plain dict shape
price_service produces, so search_service can merge it through the
existing dedupe/sort/best-deal pipeline unmodified).
"""

from dataclasses import dataclass, field
from enum import Enum

class BrandSignalSource(str, Enum):
    """Where a brand-name hint came from. Used for logging/debugging and to
    weight how much a given signal should count toward the final score."""

    LENS_BEST_GUESS = "lens_best_guess"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    GOOGLE_SHOPPING_MERCHANT = "google_shopping_merchant"
    PRODUCT_TITLE = "product_title"
    PRODUCT_TITLE_KEYWORD = "product_title_keyword"
    MERCHANT_NAME = "merchant_name"
    STRUCTURED_MANUFACTURER = "structured_manufacturer_field"
    JSON_LD_BRAND = "json_ld_brand"
    OPENGRAPH_BRAND = "opengraph_brand"
    PRODUCT_URL_DOMAIN = "product_url_domain"
    IMAGE_ALT_TEXT = "image_alt_text"

@dataclass
class BrandSignal:
    """One raw piece of evidence pointing at a candidate brand name."""

    brand_name: str
    source: BrandSignalSource
    weight: float
    raw_value: str | None = None

@dataclass
class BrandCandidate:
    """A brand name with every signal that supported it and its combined score."""

    name: str
    confidence: float
    signals: list[BrandSignal] = field(default_factory=list)

@dataclass
class BrandDetectionResult:
    """
    Output of Tier 1 (BrandDetector). `brand`/`confidence` are the winning
    candidate after ranking - `brand` is None if no signal fired at all.
    `ranked_candidates` is kept for logging/debugging even when confidence
    is too low to act on.
    """

    brand: str | None
    confidence: float
    ranked_candidates: list[BrandCandidate] = field(default_factory=list)

@dataclass
class OfficialProduct:
    """
    A product found on the brand's own official website. Shaped so it can
    be trivially converted into the same plain-dict format price_service
    produces for marketplace candidates (see service.py's `to_merge_dict`).
    """

    platform: str
    title: str
    link: str
    source_domain: str

    price: float | None = None
    currency: str | None = None
    thumbnail: str | None = None

    rating: float | None = None
    review_count: int | None = None
    availability: str | None = None
    variant_info: str | None = None

    price_source: str = "official_website"
    extraction_method: str = "none"
    confidence_score: float = 0.0

@dataclass
class BrandResolutionResult:
    """Final, public shape returned by BrandResolutionService.resolve()."""

    detected_brand: str | None
    brand_confidence: float
    official_domain: str | None = None
    official_domain_source: str | None = None
    official_product: OfficialProduct | None = None
    search_time_ms: float = 0.0
