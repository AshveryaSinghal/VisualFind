import json
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, SearchLog
from app.services import recommendation_service

def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()

def _sample_results():
    return [
        {
            "platform": "Amazon", "title": "Nike Running Shoes Men", "brand": "Nike",
            "price": "2499", "currency": "INR", "link": "https://amazon.in/x",
            "source_domain": "amazon.in", "thumbnail": None, "rating": 4.5, "review_count": 1200,
            "price_source": "google_shopping", "extraction_method": "x", "confidence_score": 0.9,
            "is_best_deal": True, "savings": None, "best_deal_reason": "cheapest",
        },
        {
            "platform": "Flipkart", "title": "Nike Running Shoes Men", "brand": "Nike",
            "price": "2599", "currency": "INR", "link": "https://flipkart.com/x",
            "source_domain": "flipkart.com", "thumbnail": None, "rating": 4.2, "review_count": 800,
            "price_source": "google_shopping", "extraction_method": "x", "confidence_score": 0.8,
            "is_best_deal": False, "savings": None, "best_deal_reason": None,
        },
    ]

def test_no_signal_returns_empty_recommendations():
    db = _session()
    result = recommendation_service.build_recommendations(db, user_id=1)
    assert result.items == []
    assert result.has_enough_signal is False

def test_recommends_from_search_history_and_category():
    db = _session()
    db.add(
        SearchLog(
            user_id=1,
            image_filename="shoe.jpg",
            best_guess_label="Nike Shoes",
            product_query="nike running shoes",
            query_source="lens",
            result_count=2,
            filtered_count=2,
            priced_count=2,
            best_deal_platform="Amazon",
            best_deal_price=2499,
            results_json=json.dumps(_sample_results()),
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    result = recommendation_service.build_recommendations(db, user_id=1)
    assert result.has_enough_signal is True
    assert len(result.items) >= 1
    reasons = {item.reason_type for item in result.items}
    assert "search_history" in reasons

    search_item = next(i for i in result.items if i.reason_type == "search_history")
    assert 'nike running shoes' in search_item.reason_text.lower()

    assert search_item.product.platform == "Amazon"

def test_other_users_history_is_never_recommended():
    db = _session()
    db.add(
        SearchLog(
            user_id=2,
            image_filename="shoe.jpg",
            product_query="nike running shoes",
            results_json=json.dumps(_sample_results()),
            created_at=datetime.now(timezone.utc),
        )
    )
    db.commit()

    result = recommendation_service.build_recommendations(db, user_id=1)
    assert result.items == []
    assert result.has_enough_signal is False
