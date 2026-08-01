"""
Core data types for the ranking engine (see engine.py for the orchestrator,
base.py for the signal interface, and signals/ for the individual scoring
strategies).

Everything here is a plain dataclass on purpose, not an ORM or pydantic
model: the ranking engine has to work directly on ProductIndexEntry rows,
on Google-Lens-sourced dicts, and on plain test doubles alike, and it must
stay importable without pulling in SQLAlchemy or FastAPI. The one-time
translation from "real request/DB state" to these types happens in
context_builders.py and in app/services/product_index/service.py; nothing
under signals/ ever touches a database.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class UserPreferenceSnapshot:
    """Mirrors app.services.preferences_service's shape, decoupled from the
    UserPreference ORM row so ranking signals never need a DB session."""

    favorite_categories: list[str] = field(default_factory=list)
    preferred_platforms: list[str] = field(default_factory=list)
    budget_min: float | None = None
    budget_max: float | None = None
    shopping_style: str | None = None


@dataclass
class SearchHistorySnapshot:
    """Lightweight, frequency-weighted summary of a user's recent search
    activity - never raw SearchLog rows, so signals never need to query the
    database themselves (see context_builders.py, the only place that
    reads SearchLog)."""

    brand_counts: dict[str, int] = field(default_factory=dict)
    category_counts: dict[str, int] = field(default_factory=dict)
    query_terms: list[str] = field(default_factory=list)

    def brand_share(self, brand: str | None) -> float | None:
        """What fraction of this user's recent searches mention `brand`.
        None if there's nothing to compare against (no history, or no
        brand given) - callers must treat that as "no opinion", not zero."""
        if not brand or not self.brand_counts:
            return None
        total = sum(self.brand_counts.values())
        if total == 0:
            return None
        return self.brand_counts.get(brand.strip().lower(), 0) / total

    def category_share(self, category: str | None) -> float | None:
        if not category or not self.category_counts:
            return None
        total = sum(self.category_counts.values())
        if total == 0:
            return None
        return self.category_counts.get(category, 0) / total


@dataclass
class RankingContext:
    """Everything one RankingSignal might need to score one candidate
    against one query. Built fresh per (candidate, query) pair by whoever
    orchestrates a ranking run (see product_index/service.py::rank_matches
    and ::rank_similar) - signals only ever read from it.
    """

    candidate: Any  # the object being scored - duck-typed (title/brand/category/price/rating/review_count/source/times_seen/created_at/updated_at)

    # What the candidate is being compared against. For a product-to-product
    # lookup these come from a real query product's own fields; for a bare
    # image upload (no product row exists yet) callers fall back to a
    # pseudo-query - see rank_matches()'s docstring for exactly how.
    query_brand: str | None = None
    query_category: str | None = None
    query_price: float | None = None
    query_title: str | None = None

    # 0..1 cosine similarity against the query image/embedding, computed
    # upstream by app/services/product_index/embedding_service.py. Never
    # recomputed here.
    visual_similarity: float | None = None

    # Free-text terms from a hybrid (image + text) or text-only search -
    # e.g. "white version", "same but leather" with the budget phrase
    # already stripped out (see app/services/hybrid_search/query_parser.py).
    # Read by TextRelevanceSignal; None for a plain image-only search.
    query_text: str | None = None

    user_preferences: UserPreferenceSnapshot | None = None
    search_history: SearchHistorySnapshot | None = None

    # Candidate-set-relative normalization references, computed once per
    # ranking call (see product_index/service.py) so no individual signal
    # needs its own query/aggregation pass over the candidate pool.
    reference_max_review_count: int = 0
    reference_max_times_seen: int = 0
    reference_now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Forward-compat bucket: a brand-new signal that needs one more datum
    # nothing above carries yet can stash/read it here without touching
    # this dataclass, the engine, or any other signal.
    extra: dict = field(default_factory=dict)


@dataclass
class SignalOutcome:
    """What a single RankingSignal.score() call returns for one candidate."""

    value: float | None  # 0..1, or None if this signal has nothing to say about this candidate
    explanation: str


@dataclass
class SignalContribution:
    """One line of a candidate's explanation: what one signal contributed
    (or why it didn't)."""

    name: str
    weight: float
    raw_score: float | None
    weighted_score: float
    applied: bool
    explanation: str


@dataclass
class RankedScore:
    total_score: float
    contributions: list[SignalContribution]
    summary: str


@dataclass
class RankedProduct:
    candidate: Any
    score: RankedScore
