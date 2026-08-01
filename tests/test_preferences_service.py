from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import PreferencesUpdateRequest, ShoppingStyle
from app.services import preferences_service

def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()

def test_categorize_text_matches_known_keyword():
    assert preferences_service.categorize_text("Nike Running Shoes Men") == "footwear"
    assert preferences_service.categorize_text("Sony wireless headphones") == "electronics"

def test_categorize_text_returns_none_for_unmatched_text():
    assert preferences_service.categorize_text("something completely unrelated xyz") is None
    assert preferences_service.categorize_text(None) is None

def test_list_category_options_covers_every_keyword_bucket():
    options = preferences_service.list_category_options()
    values = {o["value"] for o in options}
    assert values == set(preferences_service.CATEGORY_KEYWORDS.keys())

def test_upsert_and_get_preferences_round_trips():
    db = _session()
    body = PreferencesUpdateRequest(
        favorite_categories=["electronics", "not-a-real-category"],
        preferred_platforms=["Amazon", "Amazon"],
        budget_min=500,
        budget_max=2000,
        shopping_style=ShoppingStyle.BEST_VALUE,
    )
    preferences_service.upsert_preferences(db, user_id=1, body=body)

    pref = preferences_service.get_preferences(db, user_id=1)
    response = preferences_service.to_response(pref)

    assert response.favorite_categories == ["electronics"]

    assert response.preferred_platforms == ["Amazon"]
    assert response.budget_min == 500
    assert response.budget_max == 2000
    assert response.shopping_style == ShoppingStyle.BEST_VALUE

def test_upsert_preferences_swaps_inverted_budget_range():
    db = _session()
    body = PreferencesUpdateRequest(budget_min=5000, budget_max=1000)
    pref = preferences_service.upsert_preferences(db, user_id=1, body=body)
    assert pref.budget_min == 1000
    assert pref.budget_max == 5000

def test_get_preferences_returns_none_when_never_saved():
    db = _session()
    assert preferences_service.get_preferences(db, user_id=99) is None

    response = preferences_service.to_response(None)
    assert response.favorite_categories == []
    assert response.shopping_style is None
