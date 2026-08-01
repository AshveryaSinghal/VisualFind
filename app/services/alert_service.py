"""
Price Alerts: "notify me when the price of X falls below ₹Y".

Alerts are checked opportunistically every time a real price is recorded
for a product (see price_history_service.record_and_compare, which calls
check_and_trigger_alerts below right after it persists a new price point).
There is no separate polling/cron job - an alert only fires the next time
that product happens to be searched or viewed again, same as the rest of
this app's price tracking.
"""

import logging

from sqlalchemy.orm import Session

from app.database import Notification, PriceAlert
from app.models import PriceAlertCreateRequest
from app.services.price_history_service import normalize_product_key

logger = logging.getLogger(__name__)

def create_alert(db: Session, user_id: int, body: PriceAlertCreateRequest) -> PriceAlert:
    alert = PriceAlert(
        user_id=user_id,
        product_name=body.product_name.strip(),
        product_key=normalize_product_key(body.product_name),
        target_price=body.target_price,
        currency=body.currency or "INR",
        platform=body.platform,
        thumbnail=body.thumbnail,
        link=body.link,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert

def list_alerts(db: Session, user_id: int) -> list[PriceAlert]:
    return (
        db.query(PriceAlert)
        .filter(PriceAlert.user_id == user_id)
        .order_by(PriceAlert.created_at.desc())
        .all()
    )

def delete_alert(db: Session, user_id: int, alert_id: int) -> bool:
    alert = (
        db.query(PriceAlert)
        .filter(PriceAlert.id == alert_id, PriceAlert.user_id == user_id)
        .first()
    )
    if not alert:
        return False
    db.delete(alert)
    db.commit()
    return True

def check_and_trigger_alerts(
    db: Session,
    *,
    product_key: str,
    price: float,
    marketplace: str | None = None,
    currency: str | None = None,
) -> int:
    """Fires (creates a Notification for) every still-active alert whose
    product_key matches and whose target has been met. Returns how many
    fired. Deliberately never raises - a failure here should never break
    the search/view flow that triggered it."""
    if not product_key or price is None:
        return 0

    try:
        matching = (
            db.query(PriceAlert)
            .filter(
                PriceAlert.product_key == product_key,
                PriceAlert.is_active == 1,
                PriceAlert.target_price >= price,
            )
            .all()
        )
        fired = 0
        for alert in matching:
            alert.is_active = 0
            alert.triggered_price = price
            from datetime import datetime, timezone

            alert.triggered_at = datetime.now(timezone.utc)

            platform_note = f" on {marketplace}" if marketplace else ""
            currency_symbol = currency or alert.currency or ""
            db.add(
                Notification(
                    user_id=alert.user_id,
                    alert_id=alert.id,
                    type="price_alert",
                    title="Price drop alert",
                    message=(
                        f"{alert.product_name} just dropped to {currency_symbol} {price:g}"
                        f"{platform_note} - at or below your target of "
                        f"{currency_symbol} {alert.target_price:g}."
                    ),
                )
            )
            fired += 1
        if fired:
            db.commit()
        return fired
    except Exception:
        logger.exception("Price alert check failed for product_key=%s", product_key)
        db.rollback()
        return 0
