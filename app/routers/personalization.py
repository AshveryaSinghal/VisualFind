"""
HTTP layer for the personalization features: saved preferences, activity-
based recommendations, price alerts, and the in-app notifications those
alerts create. Same convention as the rest of the routers - validate here,
business logic lives in app/services/*.

Purely additive: does not import from or change the behavior of any
existing router.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import User, ViewedProduct, get_db
from app.deps import get_current_user
from app.models import (
    NotificationResponse,
    PreferencesResponse,
    PreferencesUpdateRequest,
    PriceAlertCreateRequest,
    PriceAlertResponse,
    RecommendationsResponse,
    SavedProductCreateRequest,
    SavedProductResponse,
    ViewedProductLogRequest,
)
from app.services import (
    alert_service,
    notification_service,
    preferences_service,
    recommendation_service,
    saved_products_service,
)
from app.services.price_history_service import normalize_product_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["personalization"])

@router.get("/preferences/categories", response_model=list[dict])
def get_category_options():
    """The fixed, transparent category catalogue used both for picking
    favorite categories and for matching products against them."""
    return preferences_service.list_category_options()

@router.get("/preferences", response_model=PreferencesResponse)
def get_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pref = preferences_service.get_preferences(db, current_user.id)
    return preferences_service.to_response(pref)

@router.put("/preferences", response_model=PreferencesResponse)
def update_preferences(
    body: PreferencesUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pref = preferences_service.upsert_preferences(db, current_user.id, body)
    return preferences_service.to_response(pref)

@router.get("/recommendations", response_model=RecommendationsResponse)
def get_recommendations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return recommendation_service.build_recommendations(db, current_user.id)

@router.post("/recommendations/track-view", status_code=status.HTTP_204_NO_CONTENT)
def track_view(
    body: ViewedProductLogRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Explicit 'I looked at this' ping the frontend can send from a product
    card, on top of the implicit view already logged when the full Product
    Analytics page opens (see app/routers/products.py)."""
    db.add(
        ViewedProduct(
            user_id=current_user.id,
            product_key=normalize_product_key(body.title),
            product_name=body.title,
            platform=body.platform,
            price=body.price,
            currency=body.currency,
            thumbnail=body.thumbnail,
            link=body.link,
        )
    )
    db.commit()
    return None

@router.post("/saved", response_model=SavedProductResponse, status_code=status.HTTP_201_CREATED)
def save_product(
    body: SavedProductCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Idempotent - saving a product already on the list just returns it,
    see app/services/saved_products_service.py::save_product."""
    return saved_products_service.save_product(db, current_user.id, body)

@router.get("/saved", response_model=list[SavedProductResponse])
def list_saved_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return saved_products_service.list_saved_products(db, current_user.id)

@router.delete("/saved/{saved_id}", status_code=status.HTTP_204_NO_CONTENT)
def unsave_product(
    saved_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = saved_products_service.unsave_product(db, current_user.id, saved_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Saved product not found")
    return None

@router.post("/alerts", response_model=PriceAlertResponse, status_code=status.HTTP_201_CREATED)
def create_price_alert(
    body: PriceAlertCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    alert = alert_service.create_alert(db, current_user.id, body)
    return alert

@router.get("/alerts", response_model=list[PriceAlertResponse])
def list_price_alerts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return alert_service.list_alerts(db, current_user.id)

@router.delete("/alerts/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_price_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = alert_service.delete_alert(db, current_user.id, alert_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Alert not found")
    return None

@router.get("/notifications", response_model=list[NotificationResponse])
def list_notifications(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return notification_service.list_notifications(db, current_user.id)

@router.get("/notifications/unread-count", response_model=dict)
def unread_notification_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return {"count": notification_service.unread_count(db, current_user.id)}

@router.post("/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ok = notification_service.mark_read(db, current_user.id, notification_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Notification not found")
    return None

@router.post("/notifications/read-all", status_code=status.HTTP_204_NO_CONTENT)
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    notification_service.mark_all_read(db, current_user.id)
    return None

@router.delete("/notifications/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ok = notification_service.delete_notification(db, current_user.id, notification_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Notification not found")
    return None
