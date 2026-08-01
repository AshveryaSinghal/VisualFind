"""
Integration tests for app/services/hybrid_search/service.py -
process_hybrid_search()'s three modes (image only, text only, image+text).
Google Lens (via search_service.process_image_search) is always the
primary pipeline for the image half of a hybrid search; the image+text
path just re-ranks whatever that pipeline returns (Lens results, plus any
supplemental internal-index recommendations it may have appended) by text
relevance/budget.

The plain image/text pipelines (search_service.process_image_search,
text_search_service.process_text_search) are monkeypatched with simple
stand-ins, so these tests never make a real network call and never depend
on those modules' own internals - only on the fact that
process_hybrid_search calls them and passes their result
through/post-processes it correctly. The Ranking Engine itself is
exercised for real (no monkeypatching of it).
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import PurchaseLink, SearchResponse
from app.services import hybrid_search
from app.services import search_service, text_search_service
from app.services.hybrid_search.service import InvalidHybridSearchError


def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()


def _link(title, brand=None, price=None, rating=None, review_count=None, platform="Amazon"):
    return PurchaseLink(
        platform=platform,
        title=title,
        brand=brand,
        price=str(price) if price is not None else None,
        currency="INR",
        link="https://example.com/product",
        source_domain="example.com",
        rating=rating,
        review_count=review_count,
    )


def _stub_search_response(**overrides):
    base = dict(
        search_id=1,
        total_matches_found=0,
        trusted_matches_returned=0,
        priced_count=0,
        results=[],
        from_cache=False,
    )
    base.update(overrides)
    return SearchResponse(**base)


# --- mode selection / validation ---

def test_raises_when_neither_image_nor_text_is_given():
    db = _session()
    with pytest.raises(InvalidHybridSearchError):
        hybrid_search.process_hybrid_search(db)


def test_image_only_delegates_to_the_plain_image_pipeline(monkeypatch):
    db = _session()
    calls = []

    def fake_process_image_search(image_bytes, filename, db_arg, user_id=None, background_tasks=None):
        calls.append((image_bytes, filename, user_id))
        return _stub_search_response(best_guess_label="Some Product")

    monkeypatch.setattr(search_service, "process_image_search", fake_process_image_search)

    response = hybrid_search.process_hybrid_search(db, image_bytes=b"photo-bytes", filename="a.jpg", user_id=7)

    assert calls == [(b"photo-bytes", "a.jpg", 7)]
    assert response.search_mode == "image"


def test_text_only_delegates_to_the_plain_text_pipeline(monkeypatch):
    db = _session()
    calls = []

    def fake_process_text_search(query, db_arg, query_source="text", user_id=None):
        calls.append((query, query_source, user_id))
        return _stub_search_response(
            results=[_link("Black Nike Running Shoes", price=4000)],
            trusted_matches_returned=1,
            priced_count=1,
        )

    monkeypatch.setattr(text_search_service, "process_text_search", fake_process_text_search)

    response = hybrid_search.process_hybrid_search(db, text_query="Black Nike running shoes", user_id=3)

    assert calls == [("Black Nike running shoes", "hybrid_text", 3)]
    assert response.search_mode == "text"
    assert len(response.results) == 1


def test_text_only_applies_the_parsed_budget_as_a_post_filter(monkeypatch):
    db = _session()

    def fake_process_text_search(query, db_arg, query_source="text", user_id=None):
        # The budget phrase should already have been stripped before this
        # pipeline sees the query.
        assert query == "Black Nike running shoes"
        return _stub_search_response(
            results=[
                _link("Black Nike Running Shoes (Budget)", price=3000),
                _link("Black Nike Running Shoes (Premium)", price=9000),
            ],
            trusted_matches_returned=2,
            priced_count=2,
        )

    monkeypatch.setattr(text_search_service, "process_text_search", fake_process_text_search)

    response = hybrid_search.process_hybrid_search(
        db, text_query="Black Nike running shoes under 5000", user_id=None
    )

    assert response.search_mode == "text"
    assert len(response.results) == 1
    assert response.results[0].title == "Black Nike Running Shoes (Budget)"
    assert "under" in response.note.lower() or "5000" in response.note


def test_text_only_budget_filter_never_empties_a_nonempty_result_set(monkeypatch):
    db = _session()

    def fake_process_text_search(query, db_arg, query_source="text", user_id=None):
        return _stub_search_response(
            results=[_link("Premium Item", price=9000)],
            trusted_matches_returned=1,
            priced_count=1,
        )

    monkeypatch.setattr(text_search_service, "process_text_search", fake_process_text_search)

    response = hybrid_search.process_hybrid_search(db, text_query="premium item under 500", user_id=None)
    assert len(response.results) == 1  # not filtered down to zero
    assert "showing all matches" in response.note.lower()


# --- image + text: re-ranks whatever process_image_search (Lens-primary) returns ---

def test_hybrid_search_reranks_lens_results_by_text_and_budget(monkeypatch):
    """process_image_search (Google Lens, primary) may already include a
    supplemental internal-index item appended after its own results - the
    hybrid re-rank step should treat all of it as one pool and just apply
    text relevance/budget on top, regardless of which source produced
    which item."""
    db = _session()

    def fake_process_image_search(image_bytes, filename, db_arg, user_id=None, background_tasks=None):
        return _stub_search_response(
            results=[
                _link("Nike Mesh Sneakers", brand="Nike", price=8000, rating=4.0, review_count=50),
                _link("Nike Leather Sneakers", brand="Nike", price=4000, rating=4.5, review_count=200),
            ],
            trusted_matches_returned=2,
            priced_count=2,
        )

    monkeypatch.setattr(search_service, "process_image_search", fake_process_image_search)

    response = hybrid_search.process_hybrid_search(
        db, image_bytes=b"photo", filename="shoe.jpg", text_query="same but leather under 5000"
    )

    assert response.search_mode == "hybrid"
    titles = [r.title for r in response.results]
    # The over-budget mesh candidate should be filtered out even though it
    # had a (slightly) higher rating than the leather one.
    assert "Nike Mesh Sneakers" not in titles
    assert "Nike Leather Sneakers" in titles
    assert response.results[0].ranking_score is not None
    assert response.results[0].ranking_explanation


def test_hybrid_search_image_and_text_still_works_without_a_budget(monkeypatch):
    db = _session()

    def fake_process_image_search(image_bytes, filename, db_arg, user_id=None, background_tasks=None):
        return _stub_search_response(
            results=[_link("White Nike Shoes", brand="Nike", price=3000, rating=4.0, review_count=20)],
            trusted_matches_returned=1,
            priced_count=1,
        )

    monkeypatch.setattr(search_service, "process_image_search", fake_process_image_search)

    response = hybrid_search.process_hybrid_search(db, image_bytes=b"photo", text_query="white version")
    assert response.search_mode == "hybrid"
    assert len(response.results) == 1
    assert response.results[0].ranking_explanation is not None


# --- image + text: re-ranks the primary Google Lens results ---

def test_hybrid_search_filters_out_of_budget_results_after_reranking(monkeypatch):
    db = _session()

    def fake_process_image_search(image_bytes, filename, db_arg, user_id=None, background_tasks=None):
        return _stub_search_response(
            results=[
                _link("Generic Sneaker", price=2000, rating=4.0, review_count=10),
                _link("Nike Leather Sneaker", brand="Nike", price=4000, rating=4.5, review_count=200),
                _link("Nike Premium Leather Sneaker", brand="Nike", price=9000, rating=5.0, review_count=500),
            ],
            trusted_matches_returned=3,
            priced_count=3,
        )

    monkeypatch.setattr(search_service, "process_image_search", fake_process_image_search)

    response = hybrid_search.process_hybrid_search(
        db, image_bytes=b"photo", filename="shoe.jpg", text_query="same but leather under 5000"
    )

    assert response.search_mode == "hybrid"
    titles = [r.title for r in response.results]
    assert "Nike Premium Leather Sneaker" not in titles  # over budget
    assert titles[0] == "Nike Leather Sneaker"  # matches "leather" and in budget
    assert response.results[0].ranking_score is not None


# --- background_tasks forwarding ---

def test_image_only_forwards_background_tasks_to_the_plain_image_pipeline(monkeypatch):
    """So the Product Index update for a plain image search reached via
    the hybrid endpoint runs in the background, same as
    POST /api/search/image, instead of adding latency to the response."""
    db = _session()
    captured = {}

    def fake_process_image_search(image_bytes, filename, db_arg, user_id=None, background_tasks=None):
        captured["background_tasks"] = background_tasks
        return _stub_search_response(best_guess_label="Some Product")

    monkeypatch.setattr(search_service, "process_image_search", fake_process_image_search)

    sentinel = object()
    hybrid_search.process_hybrid_search(
        db, image_bytes=b"photo-bytes", filename="a.jpg", background_tasks=sentinel
    )

    assert captured["background_tasks"] is sentinel


def test_hybrid_image_and_text_forwards_background_tasks(monkeypatch):
    """Same guarantee for the image+text path, which now always routes
    through search_service.process_image_search (Google Lens, primary)."""
    db = _session()
    captured = {}

    def fake_process_image_search(image_bytes, filename, db_arg, user_id=None, background_tasks=None):
        captured["background_tasks"] = background_tasks
        return _stub_search_response(
            results=[_link("Nike Leather Sneaker", brand="Nike", price=4000, rating=4.5, review_count=200)],
            trusted_matches_returned=1,
            priced_count=1,
        )

    monkeypatch.setattr(search_service, "process_image_search", fake_process_image_search)

    sentinel = object()
    hybrid_search.process_hybrid_search(
        db,
        image_bytes=b"photo",
        filename="shoe.jpg",
        text_query="same but leather under 5000",
        background_tasks=sentinel,
    )

    assert captured["background_tasks"] is sentinel
