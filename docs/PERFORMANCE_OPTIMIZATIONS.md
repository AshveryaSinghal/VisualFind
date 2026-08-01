# VisualFind Backend — Performance Optimization Pass

Scope: backend only (`app/`). No architecture, endpoint contracts, response
shapes, or business logic changed. Every change below is additive/internal
and covered by the existing test suite (`224 passed` before and after).

All benchmarks were run in this sandbox on a synthetic catalog / simulated
I/O, not production traffic — treat the numbers as evidence the mechanism
works and roughly how it scales, not as guaranteed production deltas.

---

## 1. Parallelized live price extraction (biggest latency win)

**File:** `app/services/price_service.py`

**Problem:** `enrich_with_live_prices()` ran `_extract_price_for_candidate()`
for every trusted candidate **strictly sequentially**, in a `for` loop. Each
call is a blocking chain of up to four tiers (Google Shopping offers already
fetched → Lens price reuse → a live HTTP GET of the product page → a full
Playwright headless-browser render as last resort). None of these share
state across candidates, so there was no reason to serialize them.

**Fix:** Run the same per-candidate extraction inside a bounded
`ThreadPoolExecutor` (`settings.price_extraction_workers`, default `6`),
preserving result order via `pool.map` and every existing exception-safety
guarantee (`_extract_price_for_candidate` still can't raise out). Setting
the worker count to `1` reproduces the exact old sequential behavior.

**Measured impact** (simulated 8 candidates × 400ms blocking call each,
representative of a page fetch or render):
- Sequential: **3201 ms**
- Parallel (6 workers): **802 ms**
- **~4x faster** for this batch size; the win scales with how many trusted
  candidates a search finds and shrinks toward 1x if there's only one.

This directly reduces `total search latency` for the Google Lens fallback
path and the hybrid-search Lens fallback path, which is the slowest branch
of the whole app already (multiple external API calls).

---

## 2. Two-phase catalog scan for image search (`find_similar` / `search_by_image`)

**File:** `app/services/product_index/service.py`

**Problem:** Both functions did `db.query(ProductIndexEntry)...all()` —
loading **every column** (title, description, image_url, product_url, price,
rating, etc.) of **every** catalog row that has an embedding, just to
compute a cosine similarity score and discard all but the top `k`. As the
catalog grows this means increasing memory for ORM object construction and
increasing bytes read from SQLite, almost all of which is thrown away.

**Fix:** Split into two phases:
1. **Scoring pass** — `db.query(ProductIndexEntry.id, ProductIndexEntry.embedding_json)`
   pulls only the two columns needed to score every candidate.
2. **Hydration pass** — `_hydrate_scored_ids()` fetches full
   `ProductIndexEntry` rows in one `IN (...)` query, but *only* for the
   winning `top_k` ids, preserving score order.

Same return type (`list[tuple[ProductIndexEntry, float]]`), same filtering/
ordering semantics — verified against the existing
`tests/test_product_index_service.py` suite (all passing).

**Expected impact:** scales with catalog size and average row width. On a
catalog with meaningful `description`/multiple text fields, this can cut
the bytes transferred from SQLite and ORM object allocations during a scan
by an order of magnitude relative to hydrating every row in full — with the
benefit growing directly with catalog size and `top_k`/candidate-pool ratio.

---

## 3. Batch cosine similarity — stop recomputing the query vector's norm

**Files:** `app/services/product_index/embedding_service.py`,
`app/services/product_index/service.py`

**Problem:** The scan loop called `cosine_similarity(query_vector, candidate)`
once per candidate. Internally, `cosine_similarity()` recomputes
`sqrt(sum(x*x for x in query_vector))` on **every single call** — but the
query vector doesn't change during the scan, so this was the same
computation repeated N times for N candidates.

**Fix:** New `query_vector_norm()` + `cosine_similarity_with_query_norm()`
compute the query vector's norm exactly once per search, then reuse it for
every candidate. `cosine_similarity()` itself is untouched (still used
directly by existing tests) — this is a pure internal optimization for the
hot scan loop, numerically identical to before.

**Expected impact:** a direct CPU reduction proportional to embedding
dimensionality × catalog size; small per-call but compounds over every
candidate in every search.

---

## 4. In-process embedding-vector cache

**File:** `app/services/product_index/service.py`

**Problem:** `json.loads(entry.embedding_json)` ran for every candidate row
on **every single search**, even though the catalog's embeddings rarely
change between searches (they're only written once, at index time or
backfill time).

**Fix:** `_parse_vector_cached()` — a bounded (20k entries, cleared on
overflow) in-process dict keyed on `(row id, exact embedding_json string)`.
A cache hit requires the stored JSON string to match exactly what's cached,
so **any row whose embedding actually changes is a guaranteed cache miss**
and re-parses correctly — there's no way to serve a stale vector.

**Measured impact** (1500-row synthetic catalog, `search_by_image`,
default embedding dimension 128):
- Cold (empty cache): **79.7 ms**
- Warm (repeat searches against the same catalog, avg of 10): **24.4 ms**
- **~3.3x faster** for the common case of the catalog not having changed
  since the last search — which is most searches, most of the time.

---

## 5. Parallelized per-candidate price extraction — see #1 above.

---

## 6. Query narrowing for search-history ranking context

**File:** `app/services/ranking/context_builders.py`

**Problem:** `load_search_history_snapshot()` — called on every ranked
search for a logged-in user — loaded up to 50 **full** `SearchLog` rows
(every column: `image_filename`, `execution_time_ms`, `best_deal_price`,
...) when the function only ever reads three of them
(`product_query`, `detected_brand`, `results_json`).

**Fix:** `db.query(SearchLog.product_query, SearchLog.detected_brand,
SearchLog.results_json)` instead of `db.query(SearchLog)` — same filter,
same order, same limit, just narrower. Cuts ORM hydration overhead and the
amount of data SQLite has to read off disk for this query.

---

## 7. New/missing indexes

**File:** `app/database.py`

- **`ix_product_index_embedding_model`** (new, on `product_index.embedding_model`):
  `search_by_image()` filters on `embedding_model == <active backend>` on
  *every single image search*. This column had no index at all, meaning
  every search was a full table scan of `product_index` to apply this
  filter. Declared on the model for new databases and added via
  `CREATE INDEX IF NOT EXISTS` for existing ones (idempotent, runs on every
  startup — verified safe to run twice with no error).
- **`ix_search_logs_user_created`** (new, composite on
  `search_logs(user_id, created_at)`): matches the exact query shape of
  `load_search_history_snapshot()` — `WHERE user_id = ? ORDER BY created_at
  DESC LIMIT 50`. The previous single-column index on `user_id` let SQLite
  find the right rows but still had to sort them afterwards; the composite
  index lets it walk rows in the already-correct order and stop at 50
  without a separate sort step.

Both were verified to be created correctly on a fresh file-backed database
and to no-op safely (`CREATE INDEX IF NOT EXISTS`) when `init_db()` runs
again on an existing one.

---

## 8. SQLite PRAGMAs: WAL mode + `synchronous=NORMAL` + larger page cache

**File:** `app/database.py`

**Problem:** SQLite's default rollback-journal mode fsyncs the *main*
database file on every commit and holds an exclusive lock for the duration
of each write — meaning every search-log write, cache write, and (worse) the
indexing pipeline's per-product commit loop
(`app/services/product_index/service.py::upsert_product`, called once per
product in a batch import) blocks any concurrent reader for that duration.

**Fix:** A `connect` event listener sets, per-connection:
- `PRAGMA journal_mode=WAL` — readers no longer block behind a writer;
  commits append to a separate WAL file instead of rewriting the main DB file.
- `PRAGMA synchronous=NORMAL` — the standard, safe pairing with WAL (per
  SQLite's own documentation) that fsyncs far less often than the default
  `FULL`, while still being crash-safe for the WAL file.
- `PRAGMA cache_size=-64000` — ~64MB of page cache per connection instead of
  SQLite's small (~2MB) default, so more of the hot tables
  (`product_index`, `search_cache`) stay resident across queries.

**Verified:** confirmed `PRAGMA journal_mode` reports `wal` on a real
file-backed database after `init_db()`, and the full test suite (which uses
both file-backed and `:memory:` SQLite engines) still passes — WAL is a
correctly-documented no-op for `:memory:` databases.

This is the change with the widest blast radius: it improves every write in
the app (search logging, cache writes, the indexing pipeline's batch
upserts) and every concurrent read during a write, without touching any
query logic.

---

## 9. In-process (L1) cache in front of the DB-backed search cache

**File:** `app/services/cache_service.py`

**Problem:** `get_cached()`/`set_cached()` back `search_cache` (SQLite) and
every lookup was a DB round trip, even for a key just read moments earlier
in the same process. `price_service.fetch_offers_for_query()`'s own
docstring already documents being called twice per search (once for brand
resolution, once for price enrichment) for the same query — previously two
DB reads + two JSON decodes for data that hadn't changed.

**Fix:** An in-process dict cache (`_local_cache`) sits in front of the DB:
- `get_cached()` checks L1 first; only falls through to SQLite on a miss.
- `set_cached()` writes through to L1 immediately after a successful DB
  write, so a fresh value is visible in-process right away.
- Every L1 entry expires no later than the real DB row's own `expires_at` —
  an L1 hit can never be staler than a DB hit would have been.
- **Correctness fix applied during testing:** the cache is namespaced by
  `id(db.get_bind())` (the specific SQLAlchemy `Engine` behind the `Session`
  passed in), not just the cache key. This was caught by
  `tests/test_search_service_internal_index.py`, which uses a fresh,
  isolated in-memory database per test — an earlier, unscoped version of
  this cache leaked a cached value from one test's database into a
  different test's (separate) database. Namespacing by engine identity
  fixes this and is also the technically correct behavior for any process
  that ever holds more than one database connection — in the normal
  single-engine-per-process deployment (see `app/database.py`) this
  namespacing is free and the full speedup still applies.

**Expected impact:** eliminates redundant DB round-trips + JSON
deserialization for cache keys read more than once within the lifetime of
their TTL in the same process (documented double-call pattern in
`fetch_offers_for_query`, plus any burst of repeated identical searches).

---

## What was intentionally *not* changed

- **Indexing pipeline embedding parallelism** (`app/services/indexing/pipeline.py`)
  already uses a `ThreadPoolExecutor` for concurrent embedding downloads —
  correctly implemented, nothing to improve there.
- **`upsert_product()`'s per-call `db.commit()`** — batching commits across
  a whole pipeline run would reduce commit count further, but changes the
  function's documented "hot search path" behavior (immediate commit/refresh
  per call) that other callers rely on. Given WAL mode already makes each
  individual commit far cheaper (item 8), this was left alone rather than
  risking a behavior change for a smaller marginal gain.
- **No new dependencies** (e.g. numpy) were added for vectorized math — the
  existing codebase is deliberately dependency-light (see
  `cache_service.py`'s own docstring), and the norm-caching + two-phase-query
  changes above capture most of the available win in pure Python without
  that tradeoff.
- **Ranking engine (`app/services/ranking/engine.py`)** rebuilds signal
  weights fresh on every call by design (`build_engine()` — "always reflect
  current config, no cached instance to go stale"); this is cheap (small,
  fixed-size in-memory objects) and changing it would trade a documented
  design guarantee for a negligible gain.

---

## Verification

- `pytest tests/` — **224 passed**, 0 failed, both before this pass and
  after (with an intermediate 2-failure regression caught and fixed — see
  item 9's correctness note).
- `init_db()` run twice against a fresh file-backed SQLite database —
  confirms all new indexes and PRAGMAs apply cleanly and migrations are
  idempotent.
