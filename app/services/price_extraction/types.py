"""
Shared data shapes for the multi-stage price extraction pipeline.

Kept as plain dataclasses (not Pydantic) since these are internal,
short-lived objects that never cross the HTTP boundary - app/models.py's
PurchaseLink is the public contract; these are implementation detail.
"""

from dataclasses import dataclass, field
from enum import Enum

class PriceRole(str, Enum):
    """
    What a detected price *means*, as best we can tell from its surrounding
    label/attribute/context. Tier 6 (selection) uses this to prefer the real
    selling price over decoys found on the same page.
    """

    UNKNOWN = "unknown"
    SELLING_PRICE = "selling_price"
    LIST_PRICE = "list_price"
    SHIPPING = "shipping"
    EMI_INSTALLMENT = "emi_installment"
    DISCOUNT_PERCENT = "discount_percent"
    COUPON = "coupon"

@dataclass
class PriceCandidate:
    """One raw price sighting, before normalization/validation."""

    raw_price: object
    raw_currency: str | None = None
    role: PriceRole = PriceRole.UNKNOWN
    label: str | None = None
    context: str | None = None

@dataclass
class NormalizedCandidate:
    """A PriceCandidate after Tier 4 (currency/number normalization)."""

    value: float
    currency: str | None
    role: PriceRole
    label: str | None = None
    context: str | None = None

@dataclass
class StrategyOutcome:
    """What a single extraction strategy (Tier 1/2/3) returns."""

    strategy_name: str
    extraction_method: str
    success: bool
    candidates: list[PriceCandidate] = field(default_factory=list)
    error: str | None = None
    time_taken_ms: float = 0.0
    rating: float | None = None
    review_count: int | None = None

@dataclass
class ExtractionResult:
    """
    Tier 7 - the final, public shape returned by PriceExtractionService for
    every product, success or failure. Never raises; `price is None` and
    `price_source == "unavailable"` is the failure case.
    """

    price: float | None
    currency: str | None
    price_source: str
    extraction_method: str
    confidence_score: float
    raw_price: object = None
    rating: float | None = None
    review_count: int | None = None
