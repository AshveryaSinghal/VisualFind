"""
Integration tests for the Ranking Engine wired into
app/services/product_index/service.py: rank_matches() (bare image upload
path), rank_similar() (product-to-product path), and the
to_purchase_link()/ranked_product_to_purchase_link() glue. See
test_ranking_engine.py and test_ranking_signals.py for the engine/signals
in isolation.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import PreferencesUpdateRequest
from app.services import preferences_service
from app.services.product_index import service as index_service


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


# --- rank_matches (bare image upload: no query product, anchor-based pseudo-query) ---

def test_rank_matches_reorders_by_blended_signals_not_just_visual_similarity(monkeypatch):
    db = _session()
    # Best visual match is a cheap, unrated listing; a slightly-less-visually-
    # similar match shares the anchor's brand/category and has a great rating -
    # multi-signal ranking should be able to prefer it over pure cosine order
    # once brand/rating are weighted in.
    top_visual = index_service.upsert_product(
        db, title="Anchor Product", brand="Sony", price=1000, rating=None, source="Amazon", attempt_embedding=False
    )
    strong_all_around = index_service.upsert_product(
        db, title="Sony Rival", brand="Sony", price=1000, rating=5.0, review_count=500, source="Amazon",
        attempt_embedding=False,
    )
    matches = [(top_visual, 0.95), (strong_all_around, 0.80)]

    ranked = index_service.rank_matches(db, matches)

    assert {r.candidate.id for r in ranked} == {top_visual.id, strong_all_around.id}
    # Every candidate gets a real, explainable score.
    for r in ranked:
        assert 0.0 <= r.score.total_score <= 1.0
        assert r.score.contributions
        assert r.score.summary

    # The anchor (top_visual) is used as the pseudo-query, so it should
    # trivially match its own brand/category/price - both entries end up
    # brand/category-matching, but the better-rated one should not simply
    # inherit last place just because its raw cosine similarity was lower.
    strong_result = next(r for r in ranked if r.candidate.id == strong_all_around.id)
    rating_contribution = next(c for c in strong_result.score.contributions if c.name == "rating")
    assert rating_contribution.applied is True
    assert rating_contribution.raw_score == 1.0


def test_rank_matches_returns_empty_list_for_no_matches():
    db = _session()
    assert index_service.rank_matches(db, []) == []


def test_rank_matches_falls_back_to_visual_similarity_only_when_engine_disabled(monkeypatch):
    db = _session()
    monkeypatch.setattr(index_service.settings, "enable_ranking_engine", False)

    a = index_service.upsert_product(db, title="Product A", brand="Sony", price=100, source="Amazon", attempt_embedding=False)
    b = index_service.upsert_product(db, title="Product B", brand="Bose", price=100, source="Amazon", attempt_embedding=False)
    matches = [(a, 0.6), (b, 0.9)]

    ranked = index_service.rank_matches(db, matches)

    # Disabled engine == visual_similarity-only ranking == pure cosine order.
    assert [r.candidate.id for r in ranked] == [b.id, a.id]
    for r in ranked:
        assert [c.name for c in r.score.contributions] == ["visual_similarity"]


def test_rank_matches_incorporates_saved_user_preferences():
    db = _session()
    in_budget = index_service.upsert_product(
        db, title="Budget Pick", brand="Sony", category="electronics", price=500, source="Amazon", attempt_embedding=False
    )
    out_of_budget = index_service.upsert_product(
        db, title="Splurge Pick", brand="Sony", category="electronics", price=50000, source="Amazon", attempt_embedding=False
    )
    matches = [(in_budget, 0.85), (out_of_budget, 0.85)]

    user_id = 1
    preferences_service.upsert_preferences(
        db,
        user_id,
        PreferencesUpdateRequest(
            favorite_categories=["electronics"],
            preferred_platforms=["Amazon"],
            budget_min=100,
            budget_max=1000,
        ),
    )

    ranked = index_service.rank_matches(db, matches, user_id=user_id)
    assert ranked[0].candidate.id == in_budget.id

    pref_contribution = next(c for c in ranked[0].score.contributions if c.name == "user_preference")
    assert pref_contribution.applied is True
    assert pref_contribution.raw_score == 1.0


# --- rank_similar (product-to-product: real query product, no anchor approximation) ---

def test_rank_similar_uses_the_real_query_products_own_fields(monkeypatch):
    db = _session()
    target = index_service.upsert_product(
        db, title="Target", brand="Nike", category="footwear", price=3000, source="Amazon"
    )
    same_brand = index_service.upsert_product(
        db, title="Candidate A", brand="Nike", category="footwear", price=3200, source="Amazon", attempt_embedding=False
    )
    different_brand = index_service.upsert_product(
        db, title="Candidate B", brand="Puma", category="footwear", price=3200, source="Amazon", attempt_embedding=False
    )

    index_service._apply_embedding(target, [1.0, 0.0, 0.0])
    index_service._apply_embedding(same_brand, [0.9, 0.1, 0.0])
    index_service._apply_embedding(different_brand, [0.9, 0.1, 0.0])
    db.commit()

    ranked = index_service.rank_similar(db, target.id, top_k=5)

    ids = [r.candidate.id for r in ranked]
    assert same_brand.id in ids
    assert different_brand.id in ids
    # Same cosine similarity for both, but same_brand should outrank
    # different_brand once brand_similarity is blended in.
    assert ids.index(same_brand.id) < ids.index(different_brand.id)


def test_rank_similar_returns_empty_when_target_has_no_embedding():
    db = _session()
    target = index_service.upsert_product(db, title="No Embedding", source="Amazon", attempt_embedding=False)
    assert index_service.rank_similar(db, target.id) == []


def test_rank_similar_respects_top_k_after_reranking_a_larger_pool():
    db = _session()
    target = index_service.upsert_product(db, title="Target", brand="Nike", source="Amazon")
    index_service._apply_embedding(target, [1.0, 0.0, 0.0])
    for i in range(10):
        entry = index_service.upsert_product(db, title=f"Candidate {i}", source="Amazon", attempt_embedding=False)
        index_service._apply_embedding(entry, [0.9, 0.1, 0.0])
    db.commit()

    ranked = index_service.rank_similar(db, target.id, top_k=3, pool_size=8)
    assert len(ranked) == 3


# --- to_purchase_link / ranked_product_to_purchase_link ---

def test_to_purchase_link_stays_backwards_compatible_without_ranking_kwargs():
    db = _session()
    entry = index_service.upsert_product(db, title="Product", source="Amazon", attempt_embedding=False)
    link = index_service.to_purchase_link(entry, similarity=0.5)
    assert link.confidence_score == 0.5
    assert link.ranking_score is None
    assert link.ranking_explanation is None


def test_ranked_product_to_purchase_link_carries_the_full_explanation():
    db = _session()
    entry = index_service.upsert_product(
        db, title="Sony Headphones", brand="Sony", price=1000, rating=4.5, review_count=50, source="Amazon",
        attempt_embedding=False,
    )
    matches = [(entry, 0.9)]

    ranked = index_service.rank_matches(db, matches)
    link = index_service.ranked_product_to_purchase_link(ranked[0])

    assert link.ranking_score == ranked[0].score.total_score
    assert link.ranking_summary == ranked[0].score.summary
    assert len(link.ranking_explanation) == len(ranked[0].score.contributions)
    assert link.confidence_score == 0.9  # visual_similarity raw score, same as before ranking existed
