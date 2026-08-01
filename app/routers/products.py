"""
HTTP layer only, same convention as app/routers/search.py: validate the
request, call service functions, translate into a response. All the actual
logic lives in app/services/product_insights_service.py and
app/services/price_history_service.py.
"""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import User, ViewedProduct, get_db
from app.deps import get_current_user
from app.models import ProductAnalyticsResponse
from app.services import product_insights_service as insights
from app.services import review_sentiment_service
from app.services.price_history_service import normalize_product_key, record_and_compare

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/products", tags=["products"])

@router.get("/analytics", response_model=ProductAnalyticsResponse)
def get_product_analytics(
    title: str = Query(..., min_length=1),
    platform: str | None = Query(None),
    price: float | None = Query(None),
    currency: str | None = Query(None),
    rating: float | None = Query(None),
    review_count: int | None = Query(None),
    thumbnail: str | None = Query(None),
    link: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):

    if price is not None:
        record_and_compare(
            db,
            product_name=title,
            marketplace=platform,
            price=price,
            currency=currency,
            user_id=current_user.id,
        )

    try:
        db.add(
            ViewedProduct(
                user_id=current_user.id,
                product_key=normalize_product_key(title),
                product_name=title,
                platform=platform,
                price=price,
                currency=currency,
                thumbnail=thumbnail,
                link=link,
            )
        )
        db.commit()
    except Exception:
        logger.exception("Failed to log viewed product for user_id=%s", current_user.id)
        db.rollback()

    price_points = insights.get_price_history_points(db, title)
    direction, change_percent = insights.price_trend(price_points)

    sentiment = review_sentiment_service.get_sentiment(
        db,
        title=title,
        platform=platform,
        link=link,
        rating=rating,
        review_count=review_count,
    )
    summary, verdict = insights.build_summary(
        rating=rating, review_count=review_count, price_points=price_points
    )

    return ProductAnalyticsResponse(
        product_name=title,
        platform=platform,
        thumbnail=thumbnail,
        current_price=price,
        currency=currency,
        rating=rating,
        review_count=review_count,
        price_points=price_points,
        has_price_trend=len(price_points) >= 2,
        price_change_percent=change_percent,
        price_direction=direction,
        sentiment=sentiment,
        summary=summary,
        verdict=verdict,
    )
