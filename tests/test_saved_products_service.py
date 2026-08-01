from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, SavedProduct
from app.models import SavedProductCreateRequest
from app.services import saved_products_service
from app.services.price_history_service import normalize_product_key

def _session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)()

def _body(name: str = "Sony WH-1000XM5", **overrides) -> SavedProductCreateRequest:
    return SavedProductCreateRequest(product_name=name, platform="Amazon", price=24999, currency="INR", **overrides)

def test_save_product_normalizes_product_key():
    db = _session()
    saved = saved_products_service.save_product(db, user_id=1, body=_body())
    assert saved.product_key == normalize_product_key("Sony WH-1000XM5")

def test_save_product_is_idempotent():
    db = _session()
    first = saved_products_service.save_product(db, user_id=1, body=_body())
    second = saved_products_service.save_product(db, user_id=1, body=_body())

    assert first.id == second.id
    assert db.query(SavedProduct).count() == 1

def test_save_product_scoped_per_user():
    db = _session()
    saved_products_service.save_product(db, user_id=1, body=_body())
    saved_products_service.save_product(db, user_id=2, body=_body())

    assert db.query(SavedProduct).count() == 2

def test_list_saved_products_scoped_to_user_and_ordered_newest_first():
    db = _session()
    saved_products_service.save_product(db, user_id=1, body=_body("A"))
    saved_products_service.save_product(db, user_id=1, body=_body("B"))
    saved_products_service.save_product(db, user_id=2, body=_body("C"))

    items = saved_products_service.list_saved_products(db, user_id=1)
    assert len(items) == 2
    assert {i.product_name for i in items} == {"A", "B"}
    assert items[0].created_at >= items[1].created_at

def test_unsave_product_only_removes_own_saved_item():
    db = _session()
    saved = saved_products_service.save_product(db, user_id=1, body=_body())

    assert saved_products_service.unsave_product(db, user_id=2, saved_id=saved.id) is False
    assert saved_products_service.unsave_product(db, user_id=1, saved_id=saved.id) is True
    assert db.query(SavedProduct).count() == 0

def test_unsave_nonexistent_returns_false():
    db = _session()
    assert saved_products_service.unsave_product(db, user_id=1, saved_id=999) is False
