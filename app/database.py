"""
Database models + session handling.

Two tables:
  - search_logs   -> search history / analytics source of truth
  - search_cache  -> generic key/value cache (image-hash results, Shopping
                     query results) so we never hit SerpApi twice for the
                     same input inside the TTL window.

A tiny auto-migration runs on startup so that adding new columns here
doesn't break an existing visualfind.db from a previous run of the app.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import (
    create_engine,
    event,
    inspect,
    text,
    Column,
    ForeignKey,
    Index,
    Integer,
    Float,
    String,
    DateTime,
    Text,
)
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from app.config import settings

logger = logging.getLogger(__name__)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    # PERF: pool_pre_ping avoids handing out a dead/stale pooled connection
    # (cheap no-op ping on every SQLite checkout; matters more once
    # database_url points at a server DB, but harmless and correct here
    # too - no downside for the default sqlite:/// setup).
    pool_pre_ping=True,
)

# --- PERF: SQLite PRAGMAs for write throughput + read concurrency -----
#
# Every commit anywhere in this app (a search log, a cache write, an
# indexing-pipeline batch that upserts many products in a loop - see
# app/services/indexing/pipeline.py) hits SQLite's default rollback-journal
# mode, which fsyncs the *main* database file on every commit and takes an
# exclusive lock for the duration of each write, blocking any concurrent
# reader. WAL (write-ahead log) mode instead appends to a separate log file
# and lets readers run concurrently with a writer, and `synchronous=NORMAL`
# (safe and the documented pairing with WAL - see sqlite.org/wal.html)
# fsyncs far less often. Net effect: much cheaper commits under the
# "many small writes in a row" pattern this app already has (batch
# indexing, one row per search log), and reads (a live search) are no
# longer blocked behind a slow write. Applied per-connection via a
# `connect` event because SQLite PRAGMAs are per-connection state, not
# something `connect_args` can set.
@event.listens_for(Engine, "connect")
def _set_sqlite_pragmas(dbapi_connection, connection_record):
    if not settings.database_url.startswith("sqlite"):
        return
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        # Negative value = size in KiB (SQLite convention) - ~64MB page
        # cache per connection instead of SQLite's small (~2MB) default,
        # so more of the hot tables (product_index, search_cache) stay
        # resident across queries instead of being re-read from disk.
        cursor.execute("PRAGMA cache_size=-64000")
    finally:
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)

class SearchLog(Base):
    """Every image search + its results -> search history and analytics."""

    __tablename__ = "search_logs"

    # PERF: composite index matching load_search_history_snapshot()'s
    # actual query shape (app/services/ranking/context_builders.py) -
    # `WHERE user_id = ? ORDER BY created_at DESC LIMIT 50`, run on every
    # ranked search for a logged-in user. The existing single-column index
    # on user_id lets SQLite find the right rows but still has to sort them
    # by created_at afterwards; this composite index lets it walk straight
    # in the already-correct order and stop at 50 rows, without a separate
    # sort step - the gap grows with how much history a user has.
    __table_args__ = (Index("ix_search_logs_user_created", "user_id", "created_at"),)

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    image_filename = Column(String, nullable=False)

    image_hash = Column(String, nullable=True, index=True)

    best_guess_label = Column(String, nullable=True)

    product_query = Column(String, nullable=True)
    query_source = Column(String, nullable=True)

    result_count = Column(Integer, default=0)
    filtered_count = Column(Integer, default=0)
    priced_count = Column(Integer, default=0)

    best_deal_platform = Column(String, nullable=True)
    best_deal_price = Column(Float, nullable=True)

    execution_time_ms = Column(Integer, nullable=True)

    results_json = Column(Text, nullable=True)

    detected_brand = Column(String, nullable=True)
    brand_confidence = Column(Float, nullable=True)
    official_domain = Column(String, nullable=True)
    official_product_found = Column(Integer, default=0)

    created_at = Column(DateTime, default=_utcnow)

class User(Base):
    """A registered VisualFind account.

    Passwords are never stored in plain text - only a bcrypt hash (see
    app/security.py). country_code/timezone are set from the profile page
    and used to render every timestamp (search history, etc.) in the
    user's own local time instead of the server's.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)

    country_code = Column(String, nullable=True)
    country_name = Column(String, nullable=True)
    city = Column(String, nullable=True)
    timezone = Column(String, nullable=False, default="UTC")

    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=_utcnow)

    search_logs = relationship("SearchLog", backref="user")

class PasswordResetToken(Base):
    """One-time-use password reset tokens.

    We store a SHA-256 hash of the token, not the raw token itself, so a
    leaked database dump alone can't be used to reset anyone's password -
    the raw token only ever exists in the emailed link and in-memory just
    long enough to verify it.
    """

    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String, unique=True, index=True, nullable=False)
    created_at = Column(DateTime, default=_utcnow)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Integer, default=0)

class ProductPriceHistory(Base):
    """One row per (product, marketplace) every time it's searched.

    Lets us answer "has this exact product's price changed since I last
    checked?" without touching search_logs, which stores a full results
    blob per search rather than one row per tracked product. See
    app/services/price_history_service.py for how this is read/written.
    """

    __tablename__ = "product_price_history"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    product_key = Column(String, nullable=False, index=True)
    product_name = Column(String, nullable=False)

    marketplace = Column(String, nullable=False)
    price = Column(Float, nullable=False)
    currency = Column(String, nullable=True)

    created_at = Column(DateTime, default=_utcnow, index=True)

class UserPreference(Base):
    """One row per user - powers the Preferences tab on the Profile page
    and feeds the recommendation engine (see app/services/recommendation_service.py).

    Lists (categories/platforms) are stored as JSON-encoded text rather than
    a join table - there's no need for relational querying over them, and
    this mirrors results_json's "small JSON blob in a Text column" pattern
    already used elsewhere in this file.
    """

    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)

    favorite_categories_json = Column(Text, nullable=True)
    preferred_platforms_json = Column(Text, nullable=True)

    budget_min = Column(Float, nullable=True)
    budget_max = Column(Float, nullable=True)

    shopping_style = Column(String, nullable=True)

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    user = relationship("User", backref="preferences", uselist=False)

class ViewedProduct(Base):
    """One row per product-detail view - the natural signal for "you looked
    at this". Logged from GET /api/products/analytics, the same endpoint
    that already records a price-history point when a product page opens.
    """

    __tablename__ = "viewed_products"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    product_key = Column(String, nullable=False, index=True)
    product_name = Column(String, nullable=False)
    platform = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    currency = Column(String, nullable=True)
    thumbnail = Column(String, nullable=True)
    link = Column(String, nullable=True)

    created_at = Column(DateTime, default=_utcnow, index=True)

class ComparedProduct(Base):
    """One row per Smart Compare run - logged from POST /api/ai/compare-products."""

    __tablename__ = "compared_products"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    product_a_name = Column(String, nullable=False)
    product_a_key = Column(String, nullable=True, index=True)
    product_b_name = Column(String, nullable=False)
    product_b_key = Column(String, nullable=True, index=True)

    winner_name = Column(String, nullable=True)

    created_at = Column(DateTime, default=_utcnow, index=True)

class SavedProduct(Base):
    """A "save for later" bookmark - explicit user action (tap the Save
    button), distinct from ViewedProduct above which logs every product
    page view automatically. One row per (user, product); saving the same
    product twice is a no-op handled in app/services/saved_products_service.py
    rather than at the DB layer, so the API can return "already saved"
    instead of a 500 on a duplicate tap.
    """

    __tablename__ = "saved_products"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    product_key = Column(String, nullable=False, index=True)
    product_name = Column(String, nullable=False)
    platform = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    currency = Column(String, nullable=True)
    thumbnail = Column(String, nullable=True)
    link = Column(String, nullable=True)
    rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=_utcnow, index=True)

    __table_args__ = (
        Index("ix_saved_products_user_product_key", "user_id", "product_key", unique=True),
    )

class PriceAlert(Base):
    """A "notify me when price falls below X" rule. Checked every time a
    real price is recorded for the matching product_key (see
    app/services/price_history_service.record_and_compare and
    app/services/alert_service.py) - there is no separate polling job,
    alerts fire opportunistically off traffic the app already generates.
    """

    __tablename__ = "price_alerts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    product_name = Column(String, nullable=False)
    product_key = Column(String, nullable=False, index=True)
    target_price = Column(Float, nullable=False)
    currency = Column(String, nullable=True, default="INR")
    platform = Column(String, nullable=True)
    thumbnail = Column(String, nullable=True)
    link = Column(String, nullable=True)

    is_active = Column(Integer, default=1)
    triggered_at = Column(DateTime, nullable=True)
    triggered_price = Column(Float, nullable=True)

    created_at = Column(DateTime, default=_utcnow)

class Notification(Base):
    """An in-app notification. Currently only ever created by a triggered
    PriceAlert, but kept generic (`type`) so other features can create
    notifications the same way later without a schema change.
    """

    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    alert_id = Column(Integer, ForeignKey("price_alerts.id"), nullable=True, index=True)

    type = Column(String, nullable=False, default="price_alert")
    title = Column(String, nullable=False)
    message = Column(String, nullable=False)

    is_read = Column(Integer, default=0)
    created_at = Column(DateTime, default=_utcnow, index=True)

class ProductIndexEntry(Base):
    """VisualFind's own internal product catalog (Phase 1 of moving off a
    pure Google-Lens-scrape-and-forget pipeline).

    Every product a completed search actually surfaces gets upserted here -
    title, brand, category, image, a visual embedding of that image, price,
    rating, source marketplace, and product URL - keyed on a normalized
    (title, brand) key so re-searching the same product refreshes this row
    (price, rating, `times_seen`, `updated_at`) instead of duplicating it.

    This is what later phases query for real multimodal (image + text)
    product search, instead of round-tripping to Google Lens/Shopping on
    every request. See app/services/product_index/service.py.
    """

    __tablename__ = "product_index"

    id = Column(Integer, primary_key=True, index=True)

    product_key = Column(String, unique=True, index=True, nullable=False)

    title = Column(String, nullable=False)
    brand = Column(String, nullable=True, index=True)
    category = Column(String, nullable=True, index=True)

    image_url = Column(String, nullable=True)

    # JSON-encoded list[float]. SQLite has no native vector column, so the
    # embedding is stored as text and deserialized on read - see
    # app/services/product_index/embedding_service.py for how it's produced
    # and app/services/product_index/service.find_similar for how it's used.
    embedding_json = Column(Text, nullable=True)
    embedding_dim = Column(Integer, nullable=True)
    # Indexed: search_by_image() (app/services/product_index/service.py)
    # filters every catalog scan on `embedding_model == <active backend>`,
    # on every image search - without this index that's a full table scan
    # of product_index on every request.
    embedding_model = Column(String, nullable=True, index=True)

    description = Column(Text, nullable=True)

    price = Column(Float, nullable=True)
    currency = Column(String, nullable=True)

    rating = Column(Float, nullable=True)
    review_count = Column(Integer, nullable=True)

    source = Column(String, nullable=True, index=True)
    product_url = Column(String, nullable=True)

    # How many completed searches have surfaced this same product.
    times_seen = Column(Integer, default=1)

    # Which IndexVersion (see below) last (re)stamped this row - either the
    # version active at upsert time, or the version of the most recent full
    # rebuild that touched it (app/services/indexing/rebuild.py). Nullable:
    # rows written before versioning existed, or written while no version
    # has ever been activated, simply have no version stamped - that's not
    # an error, just "predates versioning".
    index_version = Column(Integer, nullable=True, index=True)

    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

class IndexingJob(Base):
    """Tracks one run of the indexing pipeline (app/services/indexing/) that
    isn't tied to a single live search request - a CSV upload or a partner
    API pull. A live-search indexing run (Google Lens results) is fast
    enough and small enough that it doesn't get a job row; it just runs in
    the background via FastAPI's BackgroundTasks (see
    app/services/search_service.py).

    Batch runs are scheduled the same way (BackgroundTasks) but *do* get a
    row here so the caller can poll progress/results instead of holding a
    request open for a potentially large CSV/API import.
    """

    __tablename__ = "indexing_jobs"

    id = Column(Integer, primary_key=True, index=True)

    source_type = Column(String, nullable=False)
    source_label = Column(String, nullable=True)

    status = Column(String, nullable=False, default="queued")  # queued | running | completed | failed

    total_received = Column(Integer, default=0)
    invalid = Column(Integer, default=0)
    duplicates_removed = Column(Integer, default=0)
    created = Column(Integer, default=0)
    updated = Column(Integer, default=0)
    embedded = Column(Integer, default=0)
    failed = Column(Integer, default=0)

    error_message = Column(Text, nullable=True)

    # Set only for source_type="rebuild" jobs (see
    # app/services/indexing/rebuild.py) - links the job's live progress to
    # the IndexVersion row it's building, so GET /index/jobs/{id} and
    # GET /index/versions/{id} describe the same run from two angles.
    index_version_id = Column(Integer, ForeignKey("index_versions.id"), nullable=True)

    created_at = Column(DateTime, default=_utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

class IndexVersion(Base):
    """One generation of the Product Index's search-relevant state -
    principally, which embedding backend/model every catalog row's vector
    was computed with.

    The catalog itself (ProductIndexEntry) is a single mutable table, not a
    set of immutable snapshots - VisualFind doesn't keep N full copies of
    the index around. What "versioned indexes" means here is a persisted,
    queryable history of every full-rebuild generation: exactly one version
    is ever `is_active` at a time (the generation current searches were
    last rebuilt against), older versions are kept as `archived` audit/
    rollback history, and ProductIndexEntry.index_version stamps which
    generation last touched each row - so index health monitoring can tell
    "how much of the catalog reflects the active version" without a second
    copy of the data.

    See app/services/indexing/versioning.py for the state machine
    (building -> active|failed, active -> archived) and
    app/services/indexing/rebuild.py for what actually happens during a
    build.
    """

    __tablename__ = "index_versions"

    id = Column(Integer, primary_key=True, index=True)

    # Monotonically increasing, human-facing version number (1, 2, 3, ...).
    # Distinct from `id` only in that it's guaranteed gap-free/ordered even
    # if rows are ever pruned; `id` is what other tables actually reference.
    version_number = Column(Integer, nullable=False, unique=True, index=True)

    label = Column(String, nullable=True)

    # building -> active (success) | failed ; a previously-active version
    # moves to "archived" the moment a new one becomes active.
    status = Column(String, nullable=False, default="building", index=True)

    embedding_backend = Column(String, nullable=True)

    triggered_by = Column(String, nullable=True)  # "manual" | "cli" | "scheduled"
    notes = Column(Text, nullable=True)

    total_entries = Column(Integer, default=0)
    embedded_entries = Column(Integer, default=0)
    failed_entries = Column(Integer, default=0)

    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime, default=_utcnow)
    activated_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

class IndexHealthSnapshot(Base):
    """One point-in-time result of the Index Health Monitor (see
    app/services/index_health_service.py), persisted so health can be
    trended over time instead of only ever reflecting "right now". Written
    every time GET /api/product-index/health is called with persist=True
    (the router's default) - deliberately not on a background schedule in
    this phase, same "call it and it catches up" spirit as
    backfill_embeddings.
    """

    __tablename__ = "index_health_snapshots"

    id = Column(Integer, primary_key=True, index=True)

    status = Column(String, nullable=False)  # healthy | degraded | unhealthy
    checks_json = Column(Text, nullable=False)
    issue_count = Column(Integer, default=0)

    created_at = Column(DateTime, default=_utcnow, index=True)

class SearchCache(Base):
    """Generic TTL cache. One row per cache key."""

    __tablename__ = "search_cache"

    id = Column(Integer, primary_key=True, index=True)
    cache_key = Column(String, unique=True, index=True, nullable=False)
    payload_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=_utcnow)
    expires_at = Column(DateTime, nullable=False)

_NEW_SEARCH_LOG_COLUMNS = {
    "image_hash": "VARCHAR",
    "product_query": "VARCHAR",
    "query_source": "VARCHAR",
    "priced_count": "INTEGER DEFAULT 0",
    "best_deal_platform": "VARCHAR",
    "best_deal_price": "FLOAT",
    "execution_time_ms": "INTEGER",
    "detected_brand": "VARCHAR",
    "brand_confidence": "FLOAT",
    "official_domain": "VARCHAR",
    "official_product_found": "INTEGER DEFAULT 0",
    "user_id": "INTEGER",
}

_NEW_USER_COLUMNS = {

    "username": "VARCHAR",
}

_NEW_PRODUCT_INDEX_COLUMNS = {
    "index_version": "INTEGER",
}

_NEW_INDEXING_JOB_COLUMNS = {
    "index_version_id": "INTEGER",
}

def _add_missing_columns(inspector, table_names: set[str], table: str, columns: dict[str, str]) -> None:
    if table not in table_names:
        return
    existing_columns = {col["name"] for col in inspector.get_columns(table)}
    missing = {name: coltype for name, coltype in columns.items() if name not in existing_columns}
    if not missing:
        return
    logger.info("Migrating %s table, adding columns: %s", table, list(missing))
    with engine.begin() as conn:
        for column_name, column_type in missing.items():
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column_name} {column_type}"))

# PERF: indexes added to already-existing tables (as opposed to brand-new
# tables, which Base.metadata.create_all() indexes correctly on its own).
# `CREATE INDEX IF NOT EXISTS` is naturally idempotent - safe to run on
# every startup, same "call it and it catches up" convention as the column
# migrations above.
_NEW_INDEXES = {
    "product_index": [
        ("ix_product_index_embedding_model", "embedding_model"),
    ],
    "search_logs": [
        ("ix_search_logs_user_created", "user_id, created_at"),
    ],
}

def _add_missing_indexes(table_names: set[str]) -> None:
    for table, indexes in _NEW_INDEXES.items():
        if table not in table_names:
            continue
        with engine.begin() as conn:
            for index_name, columns in indexes:
                conn.execute(text(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({columns})"))

def _migrate_existing_tables() -> None:
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    _add_missing_columns(inspector, table_names, "product_index", _NEW_PRODUCT_INDEX_COLUMNS)
    _add_missing_columns(inspector, table_names, "indexing_jobs", _NEW_INDEXING_JOB_COLUMNS)
    _add_missing_indexes(table_names)

    if "search_logs" in table_names:
        existing_columns = {col["name"] for col in inspector.get_columns("search_logs")}
        missing = {
            name: coltype
            for name, coltype in _NEW_SEARCH_LOG_COLUMNS.items()
            if name not in existing_columns
        }
        if missing:
            logger.info("Migrating search_logs table, adding columns: %s", list(missing))
            with engine.begin() as conn:
                for column_name, column_type in missing.items():
                    conn.execute(text(f"ALTER TABLE search_logs ADD COLUMN {column_name} {column_type}"))

    if "users" in table_names:
        existing_columns = {col["name"] for col in inspector.get_columns("users")}
        missing = {
            name: coltype for name, coltype in _NEW_USER_COLUMNS.items() if name not in existing_columns
        }
        if missing:
            logger.info("Migrating users table, adding columns: %s", list(missing))
            with engine.begin() as conn:
                for column_name, column_type in missing.items():
                    conn.execute(text(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}"))

                conn.execute(
                    text("CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username_unique ON users (username)")
                )

def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _migrate_existing_tables()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
