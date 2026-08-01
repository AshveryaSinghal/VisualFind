# Search Provider Abstraction + Hybrid Search Background Indexing

Scope: backend only (`app/`). No response shapes, endpoint contracts, or
business logic changed for existing behavior with the default configuration
(`settings.search_provider = "google_lens"`). Covered by an expanded test
suite (`234 passed`, up from `224`).

---

## 1. Hybrid search now indexes Lens fallback results in the background

**Files:** `app/services/hybrid_search/service.py`, `app/routers/search.py`

**Problem:** `POST /api/search/image` already ran the Indexing Pipeline
(normalize → dedupe → store → embed) via FastAPI `BackgroundTasks`, after
the response was sent. `POST /api/search/hybrid` did not: when a hybrid
search fell back to Google Lens, `process_hybrid_search()` had no
`background_tasks` parameter to forward, so `search_service.process_image_search()`
ran that same indexing work *inline*, adding it to the hybrid response's
own latency.

**Fix:** `process_hybrid_search()` and the internal `_run_hybrid()` helper
now accept an optional `background_tasks: BackgroundTasks | None`, forwarded
to `search_service.process_image_search()` on both places it's called (the
image-only delegate path, and the hybrid Lens-fallback path). The router
now supplies FastAPI's injected `BackgroundTasks` the same way
`/api/search/image` already did. Omitting it keeps indexing synchronous,
exactly as before this parameter existed - fully backward compatible for
any direct/test caller.

---

## 2. Search Provider abstraction

**New package:** `app/services/search_providers/`

**Problem:** "Identify candidate purchase links for a photo" meant, very
concretely, "call Cloudinary then call SerpApi's Google Lens engine" -
`search_service.py` imported and called those functions directly. Adding a
second visual-search backend (Bing Visual Search, a retailer's own visual
search API, ...) would have meant branching inside the pipeline itself.

**Fix:** A small interface any visual-search integration implements:

- **`base.py`** - `SearchProvider` (one abstract method, `identify(image_bytes,
  filename) -> ProviderIdentifyResult`) and `SearchProviderError`, the one
  exception type every provider is expected to raise on failure regardless
  of what it wraps internally.
- **`types.py`** - `ProviderIdentifyResult`: `candidates` (the same
  `{title, link, price, currency, thumbnail, bucket}` dict shape
  `extract_candidate_links()` has always produced, so every existing
  downstream consumer - `domain_filter`, `price_service`, `dedupe_products`,
  `query_builder`, `brand_resolution` - needs no changes), `best_guess`,
  `raw_response` (the provider's own raw payload, kept opaquely for the two
  consumers that can optionally make extra use of Lens-shaped keys when
  present - already-existing code that degrades gracefully when those keys
  are absent, since that happens today too whenever SerpApi's response is
  missing them), and `provider_name`.
- **`registry.py`** - `register_provider()` / `get_provider()` /
  `list_providers()`. `get_provider()` (no argument) is what
  `search_service.py` calls; it resolves `settings.search_provider` to a
  registered instance. This is the *only* place that decides which
  provider answers a search.
- **`google_lens.py`** - `GoogleLensProvider`, the default (and, today,
  only shipped) provider. A pure adapter: `upload_image()`,
  `google_lens_search()`, `extract_candidate_links()`, and
  `extract_best_guess()` are called exactly as before, just from here
  instead of directly from `search_service.py`. Registers itself at import
  time.

**`app/config.py`:** new `search_provider: str = "google_lens"` setting -
switching providers app-wide is a one-line change.

**`app/services/search_service.py`:** the image-identification step is now

```python
provider = get_provider()
identify_result = provider.identify(file_bytes, filename)
candidates = identify_result.candidates
best_guess = identify_result.best_guess
```

instead of direct `upload_image()` / `google_lens_search()` /
`extract_candidate_links()` / `extract_best_guess()` calls. Nothing
downstream of this point (`query_builder`, `price_service`,
`brand_resolution`, dedupe, ranking, indexing) changed.

**`app/routers/search.py`:** both `/api/search/image` and
`/api/search/hybrid` now also catch `SearchProviderError` alongside the
existing `SerpApiError` (which can still surface directly from the Google
Shopping price-lookup tier, which isn't part of the swappable provider
surface) - both map to the same `502`.

### Adding a new provider

No changes to `search_service.py`, `hybrid_search/service.py`, or any
router are ever required:

1. Implement `SearchProvider` (see `google_lens.py` for a complete
   example) - wrap whatever the new backend raises internally in
   `SearchProviderError` before it escapes `identify()`.
2. Call `register_provider(YourProvider())` at import time, and import
   that module from `search_providers/__init__.py` so it registers on
   startup.
3. Point `settings.search_provider` at its `name` (or pass
   `get_provider("your_provider_name")` for a one-off call).

### What was intentionally *not* genericized

- **`query_builder.build_product_query()`** still takes a raw-payload dict
  positionally (passed as the provider's `raw_response`) and cascades
  through `knowledge_graph` / `search_information` keys before falling
  back to candidate-derived strategies. This already degrades gracefully
  to `{}` (see `text_search_service.py`, which has always passed
  `lens_response={}` for text-only searches) - a provider with no
  equivalent metadata just returns `{}` and the candidate-based fallbacks
  take over, unchanged.
- **`brand_resolution`** (`BrandResolutionService.resolve(lens_response=...)`)
  is similarly untouched: it's a secondary consumer of the same opaque
  payload, with its own independent signal sources (product titles, URLs,
  Shopping merchant names) that don't depend on any one provider's shape.
- Neither of these needed to change for the abstraction to work, and
  leaving their (historically Lens-named) parameter names as-is kept this
  change scoped to the provider boundary rather than a project-wide rename.

---

## Verification

- `pytest tests/` - **234 passed** (224 existing + 10 new), 0 failed.
- `tests/test_search_providers.py` (new) - registry behavior,
  `GoogleLensProvider.identify()` success shape and `SerpApiError` ->
  `SearchProviderError` wrapping, and an end-to-end test that registers an
  unrelated stub provider, points `settings.search_provider` at it, and
  proves `search_service.process_image_search()` used it - with Google
  Lens/Cloudinary monkeypatched to raise if called at all.
- `tests/test_search_service_internal_index.py` - updated to patch the
  provider module (`app/services/search_providers/google_lens.py`) instead
  of the now-removed `search_service.upload_image` /
  `search_service.google_lens_search` attributes; assertions updated from
  `SerpApiError` to `SearchProviderError` to match the new wrapping.
- `tests/test_hybrid_search_service.py` - two new tests confirming
  `background_tasks` is forwarded on both the image-only delegate path and
  the hybrid Lens-fallback path.
- App boot sanity-checked: `app.main` imports cleanly, and
  `list_providers()` / `get_provider()` confirm `google_lens` is
  registered and selected by default.
