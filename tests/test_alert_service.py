from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, PriceAlert
from app.models import PriceAlertCreateRequest
from app.services import alert_service, notification_service
from app.services.price_history_service import normalize_product_key

def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()

def test_create_alert_normalizes_product_key():
    db = _session()
    alert = alert_service.create_alert(
        db, user_id=1, body=PriceAlertCreateRequest(product_name="The Sony WH-1000XM5 Combo", target_price=999)
    )
    assert alert.product_key == normalize_product_key("The Sony WH-1000XM5 Combo")
    assert alert.is_active == 1

def test_list_alerts_scoped_to_user():
    db = _session()
    alert_service.create_alert(db, user_id=1, body=PriceAlertCreateRequest(product_name="A", target_price=10))
    alert_service.create_alert(db, user_id=2, body=PriceAlertCreateRequest(product_name="B", target_price=20))

    assert len(alert_service.list_alerts(db, user_id=1)) == 1
    assert len(alert_service.list_alerts(db, user_id=2)) == 1

def test_delete_alert_only_removes_own_alert():
    db = _session()
    alert = alert_service.create_alert(db, user_id=1, body=PriceAlertCreateRequest(product_name="A", target_price=10))

    assert alert_service.delete_alert(db, user_id=2, alert_id=alert.id) is False
    assert alert_service.delete_alert(db, user_id=1, alert_id=alert.id) is True
    assert db.query(PriceAlert).count() == 0

def test_check_and_trigger_alerts_fires_notification_when_price_meets_target():
    db = _session()
    alert = alert_service.create_alert(
        db, user_id=1, body=PriceAlertCreateRequest(product_name="Sony Headphones", target_price=999)
    )

    fired = alert_service.check_and_trigger_alerts(
        db, product_key=alert.product_key, price=899, marketplace="Amazon", currency="INR"
    )
    assert fired == 1

    notifications = notification_service.list_notifications(db, user_id=1)
    assert len(notifications) == 1
    assert notifications[0].alert_id == alert.id
    assert notification_service.unread_count(db, user_id=1) == 1

    refreshed = db.query(PriceAlert).filter(PriceAlert.id == alert.id).first()
    assert refreshed.is_active == 0
    assert refreshed.triggered_price == 899

def test_check_and_trigger_alerts_ignores_price_above_target():
    db = _session()
    alert = alert_service.create_alert(
        db, user_id=1, body=PriceAlertCreateRequest(product_name="Sony Headphones", target_price=500)
    )
    fired = alert_service.check_and_trigger_alerts(db, product_key=alert.product_key, price=900)
    assert fired == 0
    assert notification_service.list_notifications(db, user_id=1) == []

def test_mark_notification_read_and_read_all():
    db = _session()
    alert = alert_service.create_alert(
        db, user_id=1, body=PriceAlertCreateRequest(product_name="X", target_price=100)
    )
    alert_service.check_and_trigger_alerts(db, product_key=alert.product_key, price=50)

    notification = notification_service.list_notifications(db, user_id=1)[0]
    assert notification_service.mark_read(db, user_id=1, notification_id=notification.id) is True
    assert notification_service.unread_count(db, user_id=1) == 0

    assert notification_service.mark_read(db, user_id=2, notification_id=notification.id) is False
