"""Simple CRUD over the Notification table - see app/database.py.
Notifications are currently only ever created by app/services/alert_service.py
when a price alert fires, but this module is generic so any future feature
can create notifications the same way."""

from sqlalchemy.orm import Session

from app.database import Notification

_LIST_LIMIT = 50

def list_notifications(db: Session, user_id: int) -> list[Notification]:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id)
        .order_by(Notification.created_at.desc())
        .limit(_LIST_LIMIT)
        .all()
    )

def unread_count(db: Session, user_id: int) -> int:
    return (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.is_read == 0)
        .count()
    )

def mark_read(db: Session, user_id: int, notification_id: int) -> bool:
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user_id)
        .first()
    )
    if not notification:
        return False
    notification.is_read = 1
    db.commit()
    return True

def mark_all_read(db: Session, user_id: int) -> None:
    db.query(Notification).filter(Notification.user_id == user_id, Notification.is_read == 0).update(
        {"is_read": 1}
    )
    db.commit()

def delete_notification(db: Session, user_id: int, notification_id: int) -> bool:
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user_id)
        .first()
    )
    if not notification:
        return False
    db.delete(notification)
    db.commit()
    return True
