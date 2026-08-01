"""
Shopping preferences: favorite categories, budget range, preferred
platforms, and shopping style. Powers the Preferences tab on the Profile
page and is the main input to app/services/recommendation_service.py.

VisualFind has no real product-catalog "category" field (results come from
Google Lens/Shopping, not a taxonomy), so categories here are a small,
transparent set of keyword buckets matched against product titles/queries
we've *actually* seen (search queries, viewed products, results). This is
the same "derive from real text rather than a database column" trade-off
used elsewhere in the app (see analytics_service.py's brand heuristic).
"""

import json
import logging

from sqlalchemy.orm import Session

from app.database import UserPreference
from app.models import PreferencesResponse, PreferencesUpdateRequest

logger = logging.getLogger(__name__)

CATEGORY_KEYWORDS: dict[str, tuple[str, list[str]]] = {
    "electronics": (
        "Electronics",
        ["laptop", "phone", "mobile", "earbuds", "headphone", "tv", "camera",
         "speaker", "smartwatch", "tablet", "charger", "power bank", "monitor"],
    ),
    "fashion": (
        "Fashion & Apparel",
        ["shirt", "tshirt", "t-shirt", "jeans", "dress", "jacket", "kurta",
         "saree", "top", "trousers", "hoodie", "clothing"],
    ),
    "footwear": (
        "Footwear",
        ["shoes", "sneakers", "sandals", "slippers", "boots", "heels", "footwear"],
    ),
    "beauty": (
        "Beauty & Personal Care",
        ["moisturizer", "skincare", "makeup", "lipstick", "shampoo", "serum",
         "perfume", "cream", "sunscreen", "cosmetic"],
    ),
    "home": (
        "Home & Kitchen",
        ["mixer", "cookware", "furniture", "mattress", "kitchen", "decor",
         "curtain", "lamp", "vacuum", "utensil"],
    ),
    "mobiles_accessories": (
        "Mobiles & Accessories",
        ["phone case", "screen guard", "mobile cover", "earphone", "cable"],
    ),
    "sports_fitness": (
        "Sports & Fitness",
        ["dumbbell", "yoga mat", "treadmill", "cricket", "football",
         "gym", "fitness band", "racket"],
    ),
    "books_stationery": (
        "Books & Stationery",
        ["book", "notebook", "pen", "stationery", "novel"],
    ),
    "toys_baby": (
        "Toys & Baby",
        ["toy", "diaper", "baby", "stroller", "kids"],
    ),
    "groceries": (
        "Groceries",
        ["grocery", "snack", "tea", "coffee", "rice", "atta", "spice"],
    ),
}

SHOPPING_STYLE_LABELS: dict[str, str] = {
    "lowest_price": "Lowest price",
    "highest_rating": "Highest rating",
    "best_value": "Best value",
    "premium": "Premium products",
}

def list_category_options() -> list[dict]:
    return [{"value": value, "label": label} for value, (label, _kw) in CATEGORY_KEYWORDS.items()]

def categorize_text(text: str | None) -> str | None:
    """Best-effort category guess for a piece of free text (a search query,
    a product title). Returns the category `value`, or None if nothing
    matched - callers must treat that as "uncategorized", never guess."""
    if not text:
        return None
    lowered = text.lower()
    for value, (_label, keywords) in CATEGORY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return value
    return None

def loads_json_list(json_text: str | None) -> list[str]:
    if not json_text:
        return []
    try:
        value = json.loads(json_text)
        return [str(v) for v in value] if isinstance(value, list) else []
    except (json.JSONDecodeError, TypeError):
        return []

def get_preferences(db: Session, user_id: int) -> UserPreference | None:
    return db.query(UserPreference).filter(UserPreference.user_id == user_id).first()

def to_response(pref: UserPreference | None) -> PreferencesResponse:
    if pref is None:
        return PreferencesResponse(favorite_categories=[], preferred_platforms=[])
    return PreferencesResponse(
        favorite_categories=loads_json_list(pref.favorite_categories_json),
        preferred_platforms=loads_json_list(pref.preferred_platforms_json),
        budget_min=pref.budget_min,
        budget_max=pref.budget_max,
        shopping_style=pref.shopping_style,
        updated_at=pref.updated_at,
    )

def upsert_preferences(
    db: Session, user_id: int, body: PreferencesUpdateRequest
) -> UserPreference:
    pref = get_preferences(db, user_id)
    if pref is None:
        pref = UserPreference(user_id=user_id)
        db.add(pref)

    valid_categories = set(CATEGORY_KEYWORDS.keys())
    pref.favorite_categories_json = json.dumps(
        [c for c in body.favorite_categories if c in valid_categories]
    )
    pref.preferred_platforms_json = json.dumps(list(dict.fromkeys(body.preferred_platforms)))

    if body.budget_min is not None and body.budget_max is not None and body.budget_min > body.budget_max:

        body.budget_min, body.budget_max = body.budget_max, body.budget_min

    pref.budget_min = body.budget_min
    pref.budget_max = body.budget_max
    pref.shopping_style = body.shopping_style.value if body.shopping_style else None

    db.commit()
    db.refresh(pref)
    return pref
