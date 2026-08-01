import math

import pytest

from app.services.product_index.vector_index import (
    FaissVectorIndex,
    ProductVectorIndexRegistry,
)

# --- FaissVectorIndex: insertion / search --------------------------------

def test_add_and_search_returns_nearest_neighbor_first():
    index = FaissVectorIndex(dim=3)
    index.add(1, [1.0, 0.0, 0.0])
    index.add(2, [0.9, 0.1, 0.0])
    index.add(3, [0.0, 1.0, 0.0])

    results = index.search([1.0, 0.0, 0.0], top_k=3)
    ids = [row_id for row_id, _score in results]
    assert ids == [1, 2, 3]
    assert results[0][1] == pytest.approx(1.0, abs=1e-5)
    assert results[0][1] > results[1][1] > results[2][1]

def test_search_clamps_top_k_to_available_vectors():
    index = FaissVectorIndex(dim=2)
    index.add(1, [1.0, 0.0])
    index.add(2, [0.0, 1.0])
    assert len(index.search([1.0, 0.0], top_k=50)) == 2

def test_search_on_empty_index_returns_empty_list():
    index = FaissVectorIndex(dim=4)
    assert index.search([1.0, 0.0, 0.0, 0.0], top_k=5) == []

def test_ntotal_and_contains_reflect_current_state():
    index = FaissVectorIndex(dim=2)
    assert index.ntotal == 0
    index.add(1, [1.0, 0.0])
    assert index.ntotal == 1
    assert 1 in index
    assert 2 not in index

# --- FaissVectorIndex: update (re-add under the same id) -----------------

def test_add_again_with_the_same_id_updates_rather_than_duplicates():
    index = FaissVectorIndex(dim=2)
    index.add(1, [1.0, 0.0])
    index.add(1, [0.0, 1.0])  # same id, new vector

    assert index.ntotal == 1
    results = index.search([0.0, 1.0], top_k=5)
    assert results == [(1, pytest.approx(1.0, abs=1e-5))]

def test_update_is_an_alias_for_add():
    index = FaissVectorIndex(dim=2)
    index.add(1, [1.0, 0.0])
    index.update(1, [0.0, 1.0])
    assert index.ntotal == 1
    assert index.search([0.0, 1.0], top_k=1)[0][0] == 1

# --- FaissVectorIndex: deletion --------------------------------------------

def test_remove_drops_a_vector_from_the_index():
    index = FaissVectorIndex(dim=2)
    index.add(1, [1.0, 0.0])
    index.add(2, [0.0, 1.0])
    index.remove(1)

    assert index.ntotal == 1
    assert 1 not in index
    ids = [row_id for row_id, _score in index.search([1.0, 0.0], top_k=5)]
    assert ids == [2]

def test_remove_of_an_unknown_id_is_a_safe_no_op():
    index = FaissVectorIndex(dim=2)
    index.add(1, [1.0, 0.0])
    index.remove(999)  # should not raise
    assert index.ntotal == 1

def test_remove_batch_drops_multiple_ids_at_once():
    index = FaissVectorIndex(dim=2)
    index.add_batch([1, 2, 3], [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
    index.remove_batch([1, 3])
    assert index.ntotal == 1
    assert 2 in index

# --- FaissVectorIndex: persistence ----------------------------------------

def test_save_and_load_round_trips_vectors_and_ids(tmp_path):
    index = FaissVectorIndex(dim=3)
    index.add(1, [1.0, 0.0, 0.0])
    index.add(2, [0.0, 1.0, 0.0])

    path = str(tmp_path / "index.faiss")
    index.save(path)

    restored = FaissVectorIndex.load(path, dim=3)
    assert restored.ntotal == 2
    assert 1 in restored and 2 in restored
    results = restored.search([1.0, 0.0, 0.0], top_k=1)
    assert results[0][0] == 1

def test_loaded_index_supports_further_insertion_and_deletion(tmp_path):
    index = FaissVectorIndex(dim=2)
    index.add(1, [1.0, 0.0])
    path = str(tmp_path / "index.faiss")
    index.save(path)

    restored = FaissVectorIndex.load(path, dim=2)
    restored.add(2, [0.0, 1.0])
    restored.remove(1)
    assert restored.ntotal == 1
    assert 2 in restored and 1 not in restored

# --- ProductVectorIndexRegistry: reconciliation ---------------------------

def test_reconcile_builds_an_index_from_scratch():
    registry = ProductVectorIndexRegistry()
    rows = [(1, "[1.0, 0.0]"), (2, "[0.0, 1.0]")]
    index = registry.reconcile(dim=2, rows=rows)
    assert index.ntotal == 2

def test_reconcile_is_a_no_op_for_unchanged_rows():
    registry = ProductVectorIndexRegistry()
    rows = [(1, "[1.0, 0.0]")]
    registry.reconcile(dim=2, rows=rows)

    index = registry._indexes[2]
    original_index_object = index._index  # underlying faiss object identity
    registry.reconcile(dim=2, rows=rows)
    assert registry._indexes[2]._index is original_index_object
    assert registry._indexes[2].ntotal == 1

def test_reconcile_picks_up_a_changed_vector():
    registry = ProductVectorIndexRegistry()
    registry.reconcile(dim=2, rows=[(1, "[1.0, 0.0]")])
    index = registry.reconcile(dim=2, rows=[(1, "[0.0, 1.0]")])

    assert index.ntotal == 1
    results = index.search([0.0, 1.0], top_k=1)
    assert results[0][0] == 1
    assert results[0][1] == pytest.approx(1.0, abs=1e-5)

def test_reconcile_removes_rows_no_longer_present():
    registry = ProductVectorIndexRegistry()
    registry.reconcile(dim=2, rows=[(1, "[1.0, 0.0]"), (2, "[0.0, 1.0]")])
    index = registry.reconcile(dim=2, rows=[(1, "[1.0, 0.0]")])

    assert index.ntotal == 1
    assert 2 not in index

def test_reconcile_keeps_separate_indexes_per_dimension():
    registry = ProductVectorIndexRegistry()
    registry.reconcile(dim=2, rows=[(1, "[1.0, 0.0]")])
    registry.reconcile(dim=3, rows=[(1, "[1.0, 0.0, 0.0]"), (2, "[0.0, 1.0, 0.0]")])

    assert registry._indexes[2].ntotal == 1
    assert registry._indexes[3].ntotal == 2

def test_reconcile_skips_unparseable_rows_without_raising():
    registry = ProductVectorIndexRegistry()
    index = registry.reconcile(dim=2, rows=[(1, "not-json"), (2, "[1.0, 0.0]")])
    assert index.ntotal == 1
    assert 2 in index

def test_reconcile_skips_rows_whose_length_does_not_match_the_dimension():
    registry = ProductVectorIndexRegistry()
    index = registry.reconcile(dim=2, rows=[(1, "[1.0, 0.0, 0.0]"), (2, "[1.0, 0.0]")])
    assert index.ntotal == 1
    assert 2 in index

# --- ProductVectorIndexRegistry: delete / stats / clear -------------------

def test_registry_delete_removes_a_single_row():
    registry = ProductVectorIndexRegistry()
    registry.reconcile(dim=2, rows=[(1, "[1.0, 0.0]"), (2, "[0.0, 1.0]")])
    registry.delete(dim=2, row_id=1)
    assert registry._indexes[2].ntotal == 1
    assert 1 not in registry._indexes[2]

def test_registry_delete_on_unseen_dimension_is_a_safe_no_op():
    registry = ProductVectorIndexRegistry()
    registry.delete(dim=99, row_id=1)  # should not raise

def test_registry_stats_reports_totals_per_dimension():
    registry = ProductVectorIndexRegistry()
    registry.reconcile(dim=2, rows=[(1, "[1.0, 0.0]")])
    registry.reconcile(dim=3, rows=[(1, "[1.0, 0.0, 0.0]"), (2, "[0.0, 1.0, 0.0]")])

    stats = registry.stats()
    assert stats["dimensions"] == [2, 3]
    assert stats["total_vectors"] == 3
    assert stats["by_dimension"] == {2: 1, 3: 2}

def test_registry_clear_drops_all_indexes():
    registry = ProductVectorIndexRegistry()
    registry.reconcile(dim=2, rows=[(1, "[1.0, 0.0]")])
    registry.clear()
    assert registry.stats() == {"dimensions": [], "total_vectors": 0, "by_dimension": {}}

# --- ProductVectorIndexRegistry: persistence ------------------------------

def test_registry_save_and_load_round_trips_multiple_dimensions(tmp_path):
    registry = ProductVectorIndexRegistry()
    registry.reconcile(dim=2, rows=[(1, "[1.0, 0.0]")])
    registry.reconcile(dim=3, rows=[(10, "[0.0, 1.0, 0.0]"), (11, "[0.0, 0.0, 1.0]")])

    directory = str(tmp_path / "faiss_index")
    registry.save(directory)

    restored = ProductVectorIndexRegistry()
    restored.load(directory)

    assert restored.stats() == registry.stats()
    assert restored._indexes[3].search([0.0, 1.0, 0.0], top_k=1)[0][0] == 10

def test_registry_load_from_a_missing_directory_is_a_safe_no_op(tmp_path):
    registry = ProductVectorIndexRegistry()
    registry.load(str(tmp_path / "does-not-exist"))
    assert registry.stats()["total_vectors"] == 0

def test_registry_load_restores_tracked_state_to_avoid_a_redundant_re_add(tmp_path):
    registry = ProductVectorIndexRegistry()
    registry.reconcile(dim=2, rows=[(1, "[1.0, 0.0]")])
    directory = str(tmp_path / "faiss_index")
    registry.save(directory)

    restored = ProductVectorIndexRegistry()
    restored.load(directory)
    # Reconciling the exact same rows again should be a no-op (tracked
    # state round-tripped through the manifest), not a fresh add.
    index = restored._indexes[2]
    original_object = index._index
    restored.reconcile(dim=2, rows=[(1, "[1.0, 0.0]")])
    assert restored._indexes[2]._index is original_object
