"""
Shared data shapes for the indexing pipeline. Kept dependency-free (plain
dataclasses, no SQLAlchemy/pydantic) so every source adapter - Google Lens
results, a CSV row, a JSON API record - can be converted into the exact
same shape before it ever reaches the pipeline, and the pipeline itself
never has to know where a product came from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SourceType(str, Enum):
    """Where a batch of RawProducts originated. Purely informational
    (logged, stored on the ProductIndexEntry.source when nothing more
    specific is known, and surfaced on IndexingJob rows) - the pipeline
    behaves identically regardless of source."""

    GOOGLE_LENS = "google_lens"
    CSV = "csv"
    API = "api"
    MANUAL = "manual"
    REBUILD = "rebuild"


@dataclass
class RawProduct:
    """One product as discovered, before normalization. Every source
    adapter in sources.py produces these; nothing downstream of
    normalize.normalize_raw_product() should read a field that isn't
    listed here.

    `external_id` is an optional caller-supplied identifier (a CSV row's
    SKU, a supplier API's product id, ...) - not used as the catalog key
    (that's still the normalized title+brand key, so the same physical
    product discovered via two different sources still collapses to one
    row) but carried through to `raw` for traceability/debugging.
    """

    title: str | None = None
    brand: str | None = None
    category: str | None = None
    image_url: str | None = None
    description: str | None = None
    price: float | str | None = None
    currency: str | None = None
    rating: float | None = None
    review_count: int | None = None
    source: str | None = None
    product_url: str | None = None
    external_id: str | None = None
    raw: dict = field(default_factory=dict)


@dataclass
class IndexingResult:
    """Summary of one pipeline run. Every count is disjoint from every
    other (a product is exactly one of created/updated/failed after
    dedup), so `created + updated + failed == normalized - duplicates`.
    """

    source_type: SourceType
    total_received: int = 0
    invalid: int = 0
    duplicates_removed: int = 0
    created: int = 0
    updated: int = 0
    embedded: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    # Wall-clock time the whole run took, stamped by IndexingPipeline.run()
    # itself (see pipeline.py) - independent of whether a caller also
    # tracks it via an IndexingJob row's started_at/completed_at, so
    # in-process callers (e.g. product_index_service.index_purchase_links())
    # that never create a job row still get a duration back.
    duration_ms: int = 0

    # The actual stored ORM rows, in the order they were processed. Not
    # included in to_dict() (not JSON-serializable, and not something a
    # persisted IndexingJob status needs) - only populated for in-process
    # callers that need the rows themselves (e.g.
    # product_index_service.index_purchase_links()'s backward-compatible
    # return value).
    entries: list = field(default_factory=list)

    @property
    def stored(self) -> int:
        return self.created + self.updated

    def to_dict(self) -> dict:
        return {
            "source_type": self.source_type.value,
            "total_received": self.total_received,
            "invalid": self.invalid,
            "duplicates_removed": self.duplicates_removed,
            "created": self.created,
            "updated": self.updated,
            "embedded": self.embedded,
            "failed": self.failed,
            "stored": self.stored,
            "duration_ms": self.duration_ms,
            "errors": self.errors[:20],
        }
