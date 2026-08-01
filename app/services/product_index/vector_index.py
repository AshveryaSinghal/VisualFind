"""
The Product Vector Index: a FAISS-backed nearest-neighbor index over the
Product Index's stored image embeddings.

Before this module, `find_similar()`/`search_by_image()` (see
product_index/service.py) scored every candidate row with a hand-rolled
Python loop: pull every (id, embedding_json) pair out of SQLite, JSON-parse
each vector, and compute cosine similarity against the query one candidate
at a time. That's an O(n) pure-Python scan per search, repeated for every
request - correct, but it doesn't scale, and it's exactly the kind of
work a real vector index (FAISS) exists to do instead, in optimized C++.

This module replaces that inner loop with `faiss.IndexFlatIP` (exact
cosine search via inner product over L2-normalized vectors), wrapped to
support the operations a live catalog needs:

  - **insertion** / **updates**  - `FaissVectorIndex.add()` upserts (an add
    for an id already present is a remove-then-add, never a duplicate).
  - **deletion**                 - `FaissVectorIndex.remove()`.
  - **persistence**              - `FaissVectorIndex.save()`/`.load()`
    (and `ProductVectorIndexRegistry.save()`/`.load()` for the
    multi-dimension case below), via `faiss.write_index`/`read_index`.
  - **fast nearest-neighbor search** - `FaissVectorIndex.search()`.

One index per embedding dimension, not one global index
----------------------------------------------------------
FAISS indexes are fixed-dimensionality: every vector added to one must
have the same length. The catalog isn't guaranteed to be single-dimension
though - different embedding backends produce different-length vectors,
and the pre-FAISS code already tolerated a catalog mixing more than one
backend/dimension at once (a mismatched-length pair just scored 0.0 - see
the old `cosine_similarity_with_query_norm`). `ProductVectorIndexRegistry`
keeps one `FaissVectorIndex` per dimension so that invariant still holds:
same-dimension vectors get real FAISS search, and cross-dimension
candidates are still accounted for (as an explicit 0.0), never dropped.

Reconciling against the database instead of requiring explicit writes
-----------------------------------------------------------------------
Catalog rows can change without going through a dedicated
"update the index" call - direct ORM mutation in a batch job, an admin
script, a test. Rather than risk the index silently drifting out of sync
with SQLite (the source of truth), `ProductVectorIndexRegistry.reconcile()`
is called on every search with the *current* full set of
`(id, embedding_json)` rows for a dimension, and does the minimal amount
of add/update/remove work to bring the index in line - tracked with the
same "the content string itself is the staleness key" trick the old
per-row `_vector_cache` in product_index/service.py used, so unchanged
rows cost a dict lookup, not a re-embed into FAISS.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from collections.abc import Sequence

import faiss
import numpy as np

logger = logging.getLogger(__name__)

_MANIFEST_FILENAME = "manifest.json"


class FaissVectorIndex:
    """One FAISS index for one fixed vector dimension.

    Vectors are L2-normalized before being stored or queried, so the
    underlying `IndexFlatIP` (inner product) computes cosine similarity.
    `IndexIDMap2` lets ids be arbitrary ints (the Product Index's own row
    ids) instead of FAISS's default sequential positions, and its
    id<->vector mapping is written out with the index itself, so a single
    file round-trips through `save()`/`load()` with no separate id-list to
    keep in sync.
    """

    def __init__(self, dim: int):
        if dim <= 0:
            raise ValueError(f"FaissVectorIndex dimension must be positive, got {dim}")
        self.dim = dim
        self._index = faiss.IndexIDMap2(faiss.IndexFlatIP(dim))
        # Mirrors the ids already inside `_index`. FAISS's own id_map holds
        # the same information, but keeping a plain Python set alongside it
        # means "is this id already present" (needed to decide whether an
        # add is an insert or an update) is an O(1) lookup instead of a
        # round-trip through the C++ layer.
        self._ids: set[int] = set()

    @property
    def ntotal(self) -> int:
        return self._index.ntotal

    def __len__(self) -> int:
        return self.ntotal

    def __contains__(self, row_id: int) -> bool:
        return row_id in self._ids

    def _as_matrix(self, vectors: Sequence[Sequence[float]] | Sequence[float]) -> np.ndarray:
        matrix = np.array(vectors, dtype=np.float32)
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)
        if matrix.shape[1] != self.dim:
            raise ValueError(f"Expected vectors of dimension {self.dim}, got {matrix.shape[1]}")
        # Guards against FAISS's normalize_L2 dividing by zero for an
        # all-zero row - leave zero vectors as zero rather than producing
        # NaNs that would poison every subsequent similarity score.
        faiss.normalize_L2(matrix)
        return matrix

    def add(self, row_id: int, vector: Sequence[float]) -> None:
        """Insert a new vector, or update the vector already stored for
        `row_id` - an add for an id that's already present transparently
        removes the old vector first, so a row's embedding never ends up
        mapped to more than one stored vector."""
        self.add_batch([row_id], [vector])

    def add_batch(self, row_ids: Sequence[int], vectors: Sequence[Sequence[float]]) -> None:
        if not row_ids:
            return
        if len(row_ids) != len(vectors):
            raise ValueError("row_ids and vectors must be the same length")

        already_present = [row_id for row_id in row_ids if row_id in self._ids]
        if already_present:
            self.remove_batch(already_present)

        matrix = self._as_matrix(vectors)
        id_array = np.array(row_ids, dtype=np.int64)
        self._index.add_with_ids(matrix, id_array)
        self._ids.update(row_ids)

    def update(self, row_id: int, vector: Sequence[float]) -> None:
        """Explicit alias for `add()` - reads better than `add()` at call
        sites that are specifically replacing an existing vector."""
        self.add(row_id, vector)

    def remove(self, row_id: int) -> None:
        self.remove_batch([row_id])

    def remove_batch(self, row_ids: Sequence[int]) -> None:
        present = [row_id for row_id in row_ids if row_id in self._ids]
        if not present:
            return
        self._index.remove_ids(np.array(present, dtype=np.int64))
        self._ids.difference_update(present)

    def search(self, query_vector: Sequence[float], top_k: int) -> list[tuple[int, float]]:
        """Returns up to `top_k` `(row_id, cosine_similarity)` pairs,
        highest similarity first. `top_k` is clamped to however many
        vectors are actually stored - asking for more than exist is not
        an error, it just returns everything there is."""
        if self.ntotal == 0 or top_k <= 0:
            return []
        matrix = self._as_matrix(query_vector)
        k = min(top_k, self.ntotal)
        scores, ids = self._index.search(matrix, k)
        return [(int(row_id), float(score)) for row_id, score in zip(ids[0], scores[0]) if row_id != -1]

    def save(self, path: str) -> None:
        faiss.write_index(self._index, path)

    @classmethod
    def load(cls, path: str, dim: int) -> "FaissVectorIndex":
        instance = cls(dim)
        instance._index = faiss.read_index(path)
        instance._ids = {int(row_id) for row_id in faiss.vector_to_array(instance._index.id_map)}
        return instance


class ProductVectorIndexRegistry:
    """Owns one `FaissVectorIndex` per embedding dimension, and keeps each
    one reconciled against whatever rows a caller currently sees in the
    database - see the module docstring for why this is reconciliation
    rather than requiring every write path to remember to call an explicit
    insert/update/delete.

    Thread-safety: one lock guards every read and write. FAISS indexes
    aren't safe for concurrent mutation, and reconcile-then-search always
    needs to happen as one atomic step from a caller's point of view (no
    other thread's reconcile should be able to interleave and hand back a
    half-updated index).
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._indexes: dict[int, FaissVectorIndex] = {}
        # dim -> {row_id: embedding_json string last synced into that dim's index}
        self._tracked: dict[int, dict[int, str]] = {}

    def _get_or_create(self, dim: int) -> FaissVectorIndex:
        index = self._indexes.get(dim)
        if index is None:
            index = FaissVectorIndex(dim)
            self._indexes[dim] = index
            self._tracked[dim] = {}
        return index

    def reconcile(self, dim: int, rows: Sequence[tuple[int, str]]) -> FaissVectorIndex:
        """`rows` is the full, current set of `(row_id, embedding_json)`
        pairs that belong in this dimension's index right now (as seen by
        the caller's own database query). Adds anything new, updates
        anything whose `embedding_json` has changed since the last
        reconcile, and removes anything that's no longer present -
        unchanged rows cost one dict lookup each, not a re-add into FAISS.
        Returns the (now up to date) index for `dim` so the caller can
        immediately search it.
        """
        with self._lock:
            index = self._get_or_create(dim)
            tracked = self._tracked[dim]

            rows_by_id = dict(rows)
            current_ids = set(rows_by_id)

            stale_ids = [row_id for row_id in tracked if row_id not in current_ids]
            if stale_ids:
                index.remove_batch(stale_ids)
                for row_id in stale_ids:
                    tracked.pop(row_id, None)

            changed_ids: list[int] = []
            changed_vectors: list[list[float]] = []
            for row_id, embedding_json in rows_by_id.items():
                if tracked.get(row_id) == embedding_json:
                    continue
                try:
                    vector = json.loads(embedding_json)
                except (TypeError, ValueError):
                    logger.warning("Skipping unparseable embedding_json for row id=%s", row_id)
                    continue
                if len(vector) != dim:
                    # Shouldn't happen (caller is expected to have already
                    # grouped rows by dimension before calling reconcile),
                    # but never let a bad row corrupt the whole index.
                    logger.warning(
                        "Skipping row id=%s: embedding length %d != index dimension %d",
                        row_id, len(vector), dim,
                    )
                    continue
                changed_ids.append(row_id)
                changed_vectors.append(vector)

            if changed_ids:
                index.add_batch(changed_ids, changed_vectors)
                for row_id in changed_ids:
                    tracked[row_id] = rows_by_id[row_id]

            return index

    def delete(self, dim: int, row_id: int) -> None:
        """Removes a single row's vector from its dimension's index, if
        present. Safe to call even if the dimension has never been seen
        (e.g. the row never had an embedding) or the id isn't currently
        indexed."""
        with self._lock:
            index = self._indexes.get(dim)
            if index is None:
                return
            index.remove(row_id)
            self._tracked.get(dim, {}).pop(row_id, None)

    def stats(self) -> dict:
        with self._lock:
            return {
                "dimensions": sorted(self._indexes),
                "total_vectors": sum(index.ntotal for index in self._indexes.values()),
                "by_dimension": {dim: index.ntotal for dim, index in self._indexes.items()},
            }

    def clear(self) -> None:
        """Drops every in-memory index/tracking state. Not used by normal
        request handling - exists for tests and for an operator explicitly
        wanting to force a from-scratch reconcile (e.g. after suspecting
        the index has drifted)."""
        with self._lock:
            self._indexes.clear()
            self._tracked.clear()

    def save(self, directory: str) -> None:
        """Persists every dimension's index (and enough bookkeeping to
        skip re-adding unchanged vectors on the next `load()`) to
        `directory`, one FAISS file per dimension plus a small manifest."""
        with self._lock:
            os.makedirs(directory, exist_ok=True)
            manifest: dict[str, dict] = {}
            for dim, index in self._indexes.items():
                filename = f"dim_{dim}.faiss"
                index.save(os.path.join(directory, filename))
                manifest[str(dim)] = {
                    "index_file": filename,
                    "tracked": self._tracked.get(dim, {}),
                }
            with open(os.path.join(directory, _MANIFEST_FILENAME), "w") as f:
                json.dump(manifest, f)
        logger.info("Product vector index persisted to %s (%d dimension(s))", directory, len(manifest))

    def load(self, directory: str) -> None:
        """Restores state saved by `save()`. Missing/corrupt files are
        logged and skipped rather than raised - a cold start with an empty
        index is always safe (the next `reconcile()` call will rebuild it
        from the database), whereas failing app startup over a stale/
        corrupted index file on disk would not be."""
        manifest_path = os.path.join(directory, _MANIFEST_FILENAME)
        if not os.path.exists(manifest_path):
            return
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
        except (OSError, json.JSONDecodeError):
            logger.warning("Product vector index manifest at %s is unreadable; starting empty", manifest_path)
            return

        with self._lock:
            loaded_dims = 0
            for dim_str, meta in manifest.items():
                try:
                    dim = int(dim_str)
                    index_path = os.path.join(directory, meta["index_file"])
                    if not os.path.exists(index_path):
                        continue
                    self._indexes[dim] = FaissVectorIndex.load(index_path, dim)
                    self._tracked[dim] = dict(meta.get("tracked", {}))
                    loaded_dims += 1
                except Exception:
                    logger.exception("Failed to load persisted vector index for dim=%s", dim_str)
        logger.info("Product vector index restored from %s (%d dimension(s))", directory, loaded_dims)


# The instance the rest of the app should use. A process-wide singleton is
# correct here for the same reason a single FAISS index would be in any
# other app: it's an in-memory structure that's meant to represent one
# consistent view of the catalog for as long as the process is alive.
default_vector_index_registry = ProductVectorIndexRegistry()
