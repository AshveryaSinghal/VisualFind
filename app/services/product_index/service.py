"""
The Product Index: VisualFind's own internal product catalog.

Phase 1 built the catalog itself: every product a completed search
actually surfaces gets upserted here - title, brand, category, image,
price, rating, source marketplace, and product URL - keyed on a
normalized (title, brand) key so re-searching the same product refreshes
its row (`times_seen`, `updated_at`, latest price/rating) instead of
duplicating it.

Phase 2 wires in the Embedding Service (see embedding_service.py): every
new product that enters the index gets its image downloaded and embedded
automatically, embeddings are never recomputed once present (unless the
configured backend has changed - see EmbeddingService.needs_embedding),
and the model doing the embedding is swappable behind that one service.

Nothing here is allowed to break a live search: every function called
from the hot search path swallows its own errors and logs instead of
raising.
"""

import json
import logging
from datetime import datetime, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.config import settings
from app.database import ProductIndexEntry
from app.models import ProductIndexItem, PurchaseLink, RankingSignalContribution
from app.services import preferences_service
from app.services.price_history_service import normalize_product_key
from app.services.price_utils import normalize_merchant_name
from app.services.product_index.embedding_service import default_embedding_service
from app.services.product_index.vector_index import default_vector_index_registry
from app.services.ranking import RankedProduct, RankingContext, RankingEngine, build_engine
from app.services.ranking.context_builders import load_search_history_snapshot, load_user_preferences

logger = logging.getLogger(__name__)

# --- PERF: in-process parsed-embedding cache ---------------------------
#
# find_similar()/search_by_image() previously ran `json.loads(row.embedding_json)`
# for *every* catalog row on *every single search* - pure CPU overhead that
# repeats identically between searches whenever the catalog hasn't changed
# (the common case: most searches don't add new products). This cache keeps
# the already-decoded vector around, keyed on (row id, exact embedding_json
# string) so it's impossible to ever serve a stale vector: if a row's
# embedding is ever updated/backfilled, its embedding_json string changes
# too, which is a guaranteed cache miss that transparently re-parses and
# re-caches. Bounded by a hard size cap (cleared wholesale on overflow,
# rather than a heavier LRU) since this is a pure speed optimization, not a
# correctness-critical structure - worst case on overflow is one extra
# search's worth of re-parsing, never a wrong answer.
_VECTOR_CACHE_MAX_ENTRIES = 20_000
_vector_cache: dict[int, tuple[str, list[float]]] = {}

def _parse_vector_cached(entry_id: int, embedding_json: str) -> list[float]:
    cached = _vector_cache.get(entry_id)
    if cached is not None and cached[0] == embedding_json:
        return cached[1]
    vector = json.loads(embedding_json)
    if len(_vector_cache) >= _VECTOR_CACHE_MAX_ENTRIES:
        _vector_cache.clear()
    _vector_cache[entry_id] = (embedding_json, vector)
    return vector

def product_key(title: str, brand: str | None, source: str | None = None) -> str:
    """Same normalization used for price-history tracking (see
    price_history_service.normalize_product_key) plus the brand, so
    "iPhone 15" from two different brands/listings-with-the-same-name don't
    collide into one catalog row.

    Public: this is the single canonical key derivation for the catalog -
    the indexing pipeline's in-batch dedup stage (see
    app/services/indexing/dedup.py) uses it too, so "is this a duplicate"
    always means the same thing whether it's decided before a DB write
    (batch dedup) or at upsert time (this module)."""
    base = normalize_product_key(title)
    if brand:
        base = f"{base}|{brand.strip().lower()}"
    return base or f"untitled|{(source or 'unknown').lower()}"

# Backwards-compatible alias for existing internal callers/tests.
_product_key = product_key

def _apply_embedding(entry: ProductIndexEntry, vector: list[float], model_name: str | None = None) -> None:
    """Directly stamps a precomputed vector onto `entry`. This bypasses
    EmbeddingService entirely (no download, no recompute-avoidance check) -
    it exists for tests and manual/administrative seeding, not for the
    normal indexing flow. Normal code should go through
    `default_embedding_service.embed_product(...)` instead."""
    entry.embedding_json = json.dumps(vector)
    entry.embedding_dim = len(vector)
    entry.embedding_model = model_name or default_embedding_service.backend.name

def upsert_product(
    db: Session,
    *,
    title: str | None,
    brand: str | None = None,
    category: str | None = None,
    image_url: str | None = None,
    description: str | None = None,
    price: float | None = None,
    currency: str | None = None,
    rating: float | None = None,
    review_count: int | None = None,
    source: str | None = None,
    product_url: str | None = None,
    attempt_embedding: bool = True,
) -> ProductIndexEntry | None:
    """Inserts a new catalog row, or refreshes an existing one keyed on a
    normalized (title, brand) key. Returns None (and logs) rather than
    raising on any failure - callers on the hot search path must never be
    broken by a catalog write going wrong.

    When `attempt_embedding` is true (the default - "whenever a new
    product enters the database, embed it"), `default_embedding_service`
    is asked to embed the row after it's created/updated. That call is a
    no-op if the row already has a current embedding - see
    EmbeddingService.needs_embedding - so re-searching an already-indexed
    product never re-downloads its image or recomputes its vector.
    """
    if not title or not title.strip():
        return None

    key = _product_key(title, brand, source)
    category = category or preferences_service.categorize_text(title)

    try:
        entry = db.query(ProductIndexEntry).filter(ProductIndexEntry.product_key == key).first()

        if entry is None:
            entry = ProductIndexEntry(
                product_key=key,
                title=title.strip(),
                brand=brand,
                category=category,
                image_url=image_url,
                description=description,
                price=price,
                currency=currency,
                rating=rating,
                review_count=review_count,
                source=source,
                product_url=product_url,
                times_seen=1,
            )
            db.add(entry)
        else:
            entry.brand = brand or entry.brand
            entry.category = entry.category or category
            entry.image_url = image_url or entry.image_url
            entry.description = description or entry.description
            if price is not None:
                entry.price = price
            entry.currency = currency or entry.currency
            if rating is not None:
                entry.rating = rating
            if review_count is not None:
                entry.review_count = review_count
            entry.source = source or entry.source
            entry.product_url = product_url or entry.product_url
            entry.times_seen = (entry.times_seen or 0) + 1

        if attempt_embedding:
            default_embedding_service.embed_product(entry, image_url=image_url or entry.image_url)

        db.commit()
        db.refresh(entry)
        return entry
    except Exception:
        logger.exception("Failed to upsert product index entry for title=%r", title)
        db.rollback()
        return None

def index_purchase_links(
    db: Session,
    links: list[PurchaseLink],
    *,
    max_new_embeddings: int | None = None,
) -> list[ProductIndexEntry]:
    """Feeds every product from a completed Google Lens/Shopping search
    through the Indexing Pipeline (app/services/indexing/) - normalize,
    dedupe, store, embed, update indexes - and returns the resulting
    catalog rows in the same order the links were given (kept for
    backward compatibility with existing callers/tests; new code that
    wants the full run summary, including counts of duplicates removed,
    should call the pipeline directly - see
    app.services.indexing.default_pipeline).

    `max_new_embeddings` is purely a latency safety valve for an unusually
    large batch of brand-new products in one search (each embedding
    attempt is a network fetch of a product thumbnail); products already
    embedded from a previous search never count against it (see
    EmbeddingService.needs_embedding - skipped instantly, not downloaded
    again). Anything skipped due to the cap is still cataloged, just
    without an embedding yet, and will be picked up by
    backfill_embeddings() later.

    Imports the pipeline lazily to avoid a circular import: the pipeline
    module itself calls back into this module (upsert_product) for the
    "store" stage.
    """
    if not settings.enable_product_index or not links:
        return []

    from app.services.indexing.pipeline import default_pipeline
    from app.services.indexing.sources import from_purchase_links
    from app.services.indexing.types import SourceType

    raw_products = from_purchase_links(links)
    result = default_pipeline.run(
        db,
        raw_products,
        source_type=SourceType.GOOGLE_LENS,
        max_new_embeddings=max_new_embeddings,
    )
    logger.info(
        "Product Index | received=%d invalid=%d duplicates=%d created=%d updated=%d embedded=%d failed=%d",
        result.total_received, result.invalid, result.duplicates_removed,
        result.created, result.updated, result.embedded, result.failed,
    )
    return result.entries

def backfill_embeddings(db: Session, limit: int = 25) -> int:
    """Computes embeddings for catalog rows that don't currently have one
    from the active backend - products indexed before embeddings were
    enabled, ones skipped by index_purchase_links()'s per-search cap, or
    (deliberately) rows whose `embedding_model` no longer matches the
    currently configured backend after a model swap. Returns how many rows
    were updated. Safe to call repeatedly/on a schedule; each call only
    handles up to `limit` rows so it stays cheap."""
    if not settings.product_index_embedding_enabled:
        return 0

    active_backend_name = default_embedding_service.backend.name

    rows = (
        db.query(ProductIndexEntry)
        .filter(ProductIndexEntry.image_url.isnot(None))
        .filter(
            or_(
                ProductIndexEntry.embedding_json.is_(None),
                ProductIndexEntry.embedding_model != active_backend_name,
            )
        )
        .order_by(ProductIndexEntry.updated_at.desc())
        .limit(limit)
        .all()
    )

    updated = 0
    for row in rows:
        if default_embedding_service.embed_product(row):
            updated += 1

    if updated:
        db.commit()
    return updated

def get_entry(db: Session, product_id: int) -> ProductIndexEntry | None:
    return db.query(ProductIndexEntry).filter(ProductIndexEntry.id == product_id).first()

def delete_entry(db: Session, product_id: int) -> bool:
    """Removes a catalog row entirely, including its vector from the FAISS
    index (see vector_index.py) if it had one. Returns True if a row was
    found and deleted, False if there was nothing to delete for that id.
    Same "never raise on the caller" convention as the rest of this
    module - a failure is logged and reported as False, not propagated."""
    try:
        entry = get_entry(db, product_id)
        if entry is None:
            return False
        dim = entry.embedding_dim
        db.delete(entry)
        db.commit()
        if dim:
            default_vector_index_registry.delete(dim, product_id)
        # Also drop it from the parsed-vector cache (see _parse_vector_cached
        # above) - not strictly required for correctness (a deleted row's id
        # simply won't be queried again in find_similar's candidate scan),
        # but there's no reason to keep a dead row's vector around either.
        _vector_cache.pop(product_id, None)
        return True
    except Exception:
        logger.exception("Failed to delete product index entry id=%s", product_id)
        db.rollback()
        return False

def list_entries(
    db: Session,
    *,
    query: str | None = None,
    category: str | None = None,
    brand: str | None = None,
    source: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[ProductIndexEntry], int]:
    """Text/filter search over the catalog. Not a semantic search - just
    title substring + exact filters - since this is the internal-catalog
    Phase 1; ranking by embedding similarity is handled separately by
    find_similar() (image-to-catalog) once a starting product is known."""
    q = db.query(ProductIndexEntry)
    if query and query.strip():
        like = f"%{query.strip().lower()}%"
        q = q.filter(func.lower(ProductIndexEntry.title).like(like))
    if category:
        q = q.filter(ProductIndexEntry.category == category)
    if brand:
        q = q.filter(func.lower(ProductIndexEntry.brand) == brand.strip().lower())
    if source:
        q = q.filter(func.lower(ProductIndexEntry.source) == source.strip().lower())

    total = q.count()
    rows = q.order_by(ProductIndexEntry.updated_at.desc()).offset(offset).limit(limit).all()
    return rows, total

def _dim_of(embedding_json: str, embedding_dim: int | None) -> int:
    """`embedding_dim` is stamped onto every row whenever its embedding is
    set (see `_apply_embedding`/`EmbeddingService.embed_product`), so this
    is normally just returning that column - only rows written before that
    column existed fall back to actually parsing the vector to measure it."""
    if embedding_dim is not None:
        return embedding_dim
    return len(_parse_vector_cached(-1, embedding_json)) if embedding_json else 0

def _faiss_search_merged(
    query_vector: list[float],
    dim: int,
    same_dim_rows: list[tuple[int, str]],
    other_dim_ids: list[int],
) -> list[tuple[int, float]]:
    """Runs the actual nearest-neighbor search: reconciles `same_dim_rows`
    into the FAISS index for `dim` (see vector_index.py) and searches it,
    then folds in `other_dim_ids` - catalog rows whose embedding is a
    different dimension than the query and therefore can't be compared to
    it - at an explicit 0.0 similarity, matching what the old pairwise
    cosine loop did for any length-mismatched pair. Returns every scored
    id, highest similarity first; callers apply their own top_k/threshold
    slicing on top of this so the merge is never asked to pre-guess how
    many results a caller ultimately wants.
    """
    scored: list[tuple[int, float]] = []
    if same_dim_rows:
        index = default_vector_index_registry.reconcile(dim, same_dim_rows)
        scored.extend(index.search(query_vector, index.ntotal))
    scored.extend((candidate_id, 0.0) for candidate_id in other_dim_ids)
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored

def find_similar(db: Session, product_id: int, top_k: int = 10) -> list[tuple[ProductIndexEntry, float]]:
    """Visual-similarity lookup within the catalog: cosine similarity over
    stored embeddings, highest first, backed by a FAISS nearest-neighbor
    index (see vector_index.py) rather than a per-candidate Python loop.
    This is the core building block of "true multimodal product search" -
    matching by what a product *looks like* using VisualFind's own
    catalog, rather than another round-trip to Google Lens. Returns [] if
    the target has no embedding yet."""
    target = get_entry(db, product_id)
    if target is None or not target.embedding_json:
        return []

    target_vector = _parse_vector_cached(target.id, target.embedding_json)
    dim = target.embedding_dim or len(target_vector)

    # PERF: this pass only pulls (id, embedding_json, embedding_dim) - not
    # every column (title, description, image_url, ...) of every catalog
    # row. Full ProductIndexEntry rows are only ever hydrated for the
    # top_k winners, after scoring. On a catalog of any real size this is
    # far less data pulled from SQLite and far less ORM-object
    # construction per search than loading every row in full just to
    # discard all but top_k of them.
    candidate_rows = (
        db.query(ProductIndexEntry.id, ProductIndexEntry.embedding_json, ProductIndexEntry.embedding_dim)
        .filter(ProductIndexEntry.id != product_id)
        .filter(ProductIndexEntry.embedding_json.isnot(None))
        .all()
    )

    same_dim_rows = []
    other_dim_ids = []
    for candidate_id, embedding_json, embedding_dim in candidate_rows:
        if _dim_of(embedding_json, embedding_dim) == dim:
            same_dim_rows.append((candidate_id, embedding_json))
        else:
            other_dim_ids.append(candidate_id)

    scored = _faiss_search_merged(target_vector, dim, same_dim_rows, other_dim_ids)
    top = scored[:top_k]
    return _hydrate_scored_ids(db, top)

def _hydrate_scored_ids(
    db: Session, scored_ids: list[tuple[int, float]]
) -> list[tuple[ProductIndexEntry, float]]:
    """Turns a [(id, score), ...] scoring result into
    [(ProductIndexEntry, score), ...], preserving the input order (highest
    score first). Fetches full rows for exactly these ids in one query -
    the "only hydrate the winners" half of the two-phase find_similar()/
    search_by_image() scoring pattern (see the PERF note in find_similar)."""
    if not scored_ids:
        return []
    ids = [entry_id for entry_id, _score in scored_ids]
    rows = db.query(ProductIndexEntry).filter(ProductIndexEntry.id.in_(ids)).all()
    by_id = {row.id: row for row in rows}
    return [(by_id[entry_id], score) for entry_id, score in scored_ids if entry_id in by_id]

def search_by_image(
    db: Session,
    image_bytes: bytes,
    *,
    top_k: int | None = None,
    min_similarity: float | None = None,
) -> list[tuple[ProductIndexEntry, float]]:
    """Phase 3: image-to-catalog search. Embeds the raw bytes of an
    *uploaded* image (not an existing catalog row - see find_similar() for
    that) with the currently active backend, then ranks every catalog row
    that already has a current embedding by cosine similarity, highest
    first, dropping anything below `min_similarity`.

    This is the entry point search_service.process_image_search calls
    before ever falling back to Google Lens. Never raises: embeddings
    disabled, an unembeddable upload, or an empty/unembedded catalog all
    just mean "no internal matches" ([]), same as any other failure on the
    hot search path.
    """
    top_k = settings.product_index_search_top_k if top_k is None else top_k
    min_similarity = (
        settings.product_index_search_min_similarity if min_similarity is None else min_similarity
    )

    if not settings.enable_product_index or not settings.product_index_embedding_enabled:
        return []
    if not image_bytes:
        return []

    backend = default_embedding_service.backend
    try:
        query_vector = backend.embed(image_bytes)
    except Exception:
        logger.debug("Could not embed uploaded image for internal index search", exc_info=True)
        return []

    dim = len(query_vector)

    # PERF: same two-phase pattern as find_similar() - score against a
    # lightweight (id, embedding_json, embedding_dim) projection instead of
    # hydrating every column of every matching catalog row, then hydrate
    # only the survivors. The actual nearest-neighbor search itself runs
    # through the FAISS index (see vector_index.py) rather than a
    # per-candidate Python loop.
    candidate_rows = (
        db.query(ProductIndexEntry.id, ProductIndexEntry.embedding_json, ProductIndexEntry.embedding_dim)
        .filter(ProductIndexEntry.embedding_json.isnot(None))
        .filter(ProductIndexEntry.embedding_model == backend.name)
        .all()
    )
    if not candidate_rows:
        return []

    same_dim_rows = []
    other_dim_ids = []
    for candidate_id, embedding_json, embedding_dim in candidate_rows:
        if _dim_of(embedding_json, embedding_dim) == dim:
            same_dim_rows.append((candidate_id, embedding_json))
        else:
            other_dim_ids.append(candidate_id)

    scored = _faiss_search_merged(query_vector, dim, same_dim_rows, other_dim_ids)
    scored = [pair for pair in scored if pair[1] >= min_similarity]
    top = scored[:top_k]
    return _hydrate_scored_ids(db, top)

def to_purchase_link(
    entry: ProductIndexEntry,
    similarity: float | None = None,
    *,
    ranking_score: float | None = None,
    ranking_explanation: list[RankingSignalContribution] | None = None,
    ranking_summary: str | None = None,
) -> PurchaseLink:
    """Catalog row -> the same PurchaseLink schema Google Lens results are
    normalized into, so a search answered straight from the internal index
    (Phase 3) can flow through the exact same downstream steps - best-deal
    scoring, quick-commerce annotation, sorting, history/analytics logging
    - as a Lens-sourced search, with no special-casing required anywhere
    else. `similarity` (the cosine score against the uploaded image, if
    this came from search_by_image) is surfaced via `confidence_score`.

    `ranking_score`/`ranking_explanation`/`ranking_summary` are optional
    and only meaningful for results that went through the Ranking Engine
    (see rank_matches()/rank_similar() and ranked_product_to_purchase_link()
    below) - plain callers (including all existing tests) can keep calling
    this with just `similarity` and get identical behavior to before.
    """
    price = entry.price
    return PurchaseLink(
        platform=normalize_merchant_name(entry.source) or entry.source or "VisualFind Index",
        title=entry.title,
        brand=entry.brand,
        price=str(price) if price is not None else None,
        currency=entry.currency,
        link=entry.product_url or "",
        source_domain=entry.source or "internal-index",
        thumbnail=entry.image_url,
        rating=entry.rating,
        review_count=entry.review_count,
        price_source="internal_index",
        extraction_method="internal_index_match",
        confidence_score=round(similarity, 4) if similarity is not None else None,
        ranking_score=ranking_score,
        ranking_explanation=ranking_explanation,
        ranking_summary=ranking_summary,
    )

def to_ranking_contribution_schema(contribution) -> RankingSignalContribution:
    """SignalContribution (plain dataclass, see app/services/ranking/types.py)
    -> the API/schema equivalent. Kept here (the ORM/schema boundary
    module) rather than inside app/services/ranking/, which is deliberately
    kept free of any dependency on pydantic/API schemas."""
    return RankingSignalContribution(
        signal=contribution.name,
        weight=contribution.weight,
        raw_score=contribution.raw_score,
        weighted_score=round(contribution.weighted_score, 4),
        applied=contribution.applied,
        explanation=contribution.explanation,
    )

def ranked_product_to_purchase_link(ranked: RankedProduct) -> PurchaseLink:
    """Same catalog-row -> PurchaseLink mapping as to_purchase_link(), but
    for a RankedProduct out of rank_matches()/rank_similar(): carries the
    full multi-signal explanation (`ranking_score`/`ranking_explanation`/
    `ranking_summary`) alongside the same plain `confidence_score` every
    existing caller already knows how to read."""
    visual_similarity = next(
        (c.raw_score for c in ranked.score.contributions if c.name == "visual_similarity"),
        None,
    )
    return to_purchase_link(
        ranked.candidate,
        similarity=visual_similarity,
        ranking_score=ranked.score.total_score,
        ranking_explanation=[to_ranking_contribution_schema(c) for c in ranked.score.contributions],
        ranking_summary=ranked.score.summary,
    )

def _reference_stats(entries: list[ProductIndexEntry]) -> tuple[int, int]:
    """Candidate-set-relative normalization ceilings for the review_count
    and popularity signals - computed once per ranking call instead of
    each signal running its own pass over the pool (see
    RankingContext.reference_max_review_count/reference_max_times_seen)."""
    review_counts = [e.review_count for e in entries if e.review_count]
    times_seen = [e.times_seen for e in entries if e.times_seen]
    return max(review_counts, default=0), max(times_seen, default=0)

def _resolve_engine(engine: RankingEngine | None) -> RankingEngine:
    if engine is not None:
        return engine
    if settings.enable_ranking_engine:
        return build_engine()
    # Ranking Engine disabled: fall back to visual_similarity alone, which
    # reproduces the old pure-cosine ordering while still returning results
    # through the same explainable RankedProduct shape - no special-cased
    # return type for callers to branch on.
    return build_engine(signal_names=["visual_similarity"])

def rank_matches(
    db: Session,
    matches: list[tuple[ProductIndexEntry, float]],
    *,
    user_id: int | None = None,
    query_text: str | None = None,
    budget_max: float | None = None,
    engine: RankingEngine | None = None,
) -> list[RankedProduct]:
    """Multi-signal re-ranking of search_by_image()'s raw cosine-similarity
    hits - the "instead of returning products only by image similarity,
    rank them using multiple signals" entry point for a bare image upload,
    and (via `query_text`/`budget_max`) for the image+text hybrid search
    path too (see app/services/hybrid_search/service.py).

    There is no real "query product" here, just an uploaded photo with no
    title/brand/category of its own - so brand/category/price comparisons
    anchor on the single best visual match (the candidate pure-cosine
    ranking already trusts most) as a pseudo-query. This keeps every
    signal meaningful without inventing product metadata that doesn't
    exist yet for a bare image. See rank_similar() for the richer case
    where a full query product *is* known.

    `query_text` (e.g. "white version", "same but leather" - budget
    phrases already stripped out by the caller) feeds TextRelevanceSignal;
    left as None this behaves exactly as before text search existed.
    `budget_max` (e.g. from "under 5000") is applied as a hard pre-filter,
    not a ranking signal - dropping every candidate priced above it before
    ranking, unless that would drop everything, in which case the filter
    is skipped rather than returning zero results for an honest visual
    match that's simply over budget.
    """
    if not matches:
        return []

    if budget_max is not None:
        within_budget = [(entry, sim) for entry, sim in matches if entry.price is None or entry.price <= budget_max]
        if within_budget:
            matches = within_budget

    engine = _resolve_engine(engine)
    entries = [entry for entry, _similarity in matches]
    max_reviews, max_seen = _reference_stats(entries)

    anchor_entry, _anchor_similarity = max(matches, key=lambda pair: pair[1])
    preferences = load_user_preferences(db, user_id)
    history = load_search_history_snapshot(db, user_id)
    reference_now = datetime.now(timezone.utc)

    contexts = [
        (
            entry,
            RankingContext(
                candidate=entry,
                query_brand=anchor_entry.brand,
                query_category=anchor_entry.category,
                query_price=anchor_entry.price,
                query_title=anchor_entry.title,
                query_text=query_text,
                visual_similarity=similarity,
                user_preferences=preferences,
                search_history=history,
                reference_max_review_count=max_reviews,
                reference_max_times_seen=max_seen,
                reference_now=reference_now,
            ),
        )
        for entry, similarity in matches
    ]
    return engine.rank(contexts)

def rank_similar(
    db: Session,
    product_id: int,
    *,
    top_k: int = 10,
    user_id: int | None = None,
    pool_size: int | None = None,
    engine: RankingEngine | None = None,
) -> list[RankedProduct]:
    """Multi-signal version of find_similar(): pulls a larger
    visual-similarity pool (`pool_size`, default
    `top_k * settings.ranking_similar_pool_multiplier`, floored at 20) so
    the non-visual signals have real candidates to reorder rather than
    just re-sorting an already-visual-only top_k, then blends in
    brand/category/price/rating/review-count/popularity/freshness plus
    this user's own preferences and search history.

    Unlike rank_matches(), the query product's own fields (brand,
    category, price) are the real comparison target here - there's no
    pseudo-query approximation needed, since `product_id` names an actual
    catalog row.
    """
    if pool_size is None:
        pool_size = max(top_k * settings.ranking_similar_pool_multiplier, 20)

    pool = find_similar(db, product_id, top_k=pool_size)
    if not pool:
        return []

    target = get_entry(db, product_id)
    engine = _resolve_engine(engine)
    entries = [entry for entry, _similarity in pool]
    max_reviews, max_seen = _reference_stats(entries)
    preferences = load_user_preferences(db, user_id)
    history = load_search_history_snapshot(db, user_id)
    reference_now = datetime.now(timezone.utc)

    contexts = [
        (
            entry,
            RankingContext(
                candidate=entry,
                query_brand=target.brand if target else None,
                query_category=target.category if target else None,
                query_price=target.price if target else None,
                query_title=target.title if target else None,
                visual_similarity=similarity,
                user_preferences=preferences,
                search_history=history,
                reference_max_review_count=max_reviews,
                reference_max_times_seen=max_seen,
                reference_now=reference_now,
            ),
        )
        for entry, similarity in pool
    ]
    return engine.rank(contexts)[:top_k]

def get_stats(db: Session) -> dict:
    total = db.query(ProductIndexEntry).count()
    with_embeddings = db.query(ProductIndexEntry).filter(ProductIndexEntry.embedding_json.isnot(None)).count()

    by_category = dict(
        db.query(ProductIndexEntry.category, func.count(ProductIndexEntry.id))
        .filter(ProductIndexEntry.category.isnot(None))
        .group_by(ProductIndexEntry.category)
        .all()
    )
    by_source = dict(
        db.query(ProductIndexEntry.source, func.count(ProductIndexEntry.id))
        .filter(ProductIndexEntry.source.isnot(None))
        .group_by(ProductIndexEntry.source)
        .all()
    )

    return {
        "total_products": total,
        "products_with_embeddings": with_embeddings,
        "by_category": by_category,
        "by_source": by_source,
    }

def to_item(entry: ProductIndexEntry) -> ProductIndexItem:
    """ORM row -> API schema. Kept here (not just in the router) so tests
    and other services can reuse it without importing FastAPI plumbing."""
    return ProductIndexItem(
        id=entry.id,
        product_key=entry.product_key,
        title=entry.title,
        brand=entry.brand,
        category=entry.category,
        image_url=entry.image_url,
        description=entry.description,
        price=entry.price,
        currency=entry.currency,
        rating=entry.rating,
        review_count=entry.review_count,
        source=entry.source,
        product_url=entry.product_url,
        has_embedding=bool(entry.embedding_json),
        embedding_dim=entry.embedding_dim,
        embedding_model=entry.embedding_model,
        times_seen=entry.times_seen or 1,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )
