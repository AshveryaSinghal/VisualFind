"""
Save for later: an explicit user bookmark on a product, separate from the
automatic ViewedProduct history log. Same conventions as alert_service.py -
thin, direct SQLAlchemy, one function per operation, no ORM-relationship
magic.
"""

import logging

from sqlalchemy.orm import Session

from app.database import SavedProduct
from app.models import SavedProductCreateRequest
from app.services.price_history_service import normalize_product_key

logger = logging.getLogger(__name__)

def save_product(db: Session, user_id: int, body: SavedProductCreateRequest) -> SavedProduct:
    """Idempotent: saving a product that's already saved just returns the
    existing row instead of raising on the unique (user_id, product_key)
    constraint - a double-tap of the Save button should never be an error."""
    product_key = normalize_product_key(body.product_name)

    existing = (
        db.query(SavedProduct)
        .filter(SavedProduct.user_id == user_id, SavedProduct.product_key == product_key)
        .first()
    )
    if existing:
        return existing

    saved = SavedProduct(
        user_id=user_id,
        product_key=product_key,
        product_name=body.product_name.strip(),
        platform=body.platform,
        price=body.price,
        currency=body.currency,
        thumbnail=body.thumbnail,
        link=body.link,
        rating=body.rating,
        review_count=body.review_count,
    )
    db.add(saved)
    try:
        db.commit()
    except Exception:
        # Race: two near-simultaneous saves of the same product both passed
        # the existence check above. The unique index rejects the second
        # write - fetch and return the row the other request just created
        # rather than surfacing a 500 for what is, from the user's
        # perspective, a successful save.
        db.rollback()
        existing = (
            db.query(SavedProduct)
            .filter(SavedProduct.user_id == user_id, SavedProduct.product_key == product_key)
            .first()
        )
        if existing:
            return existing
        raise
    db.refresh(saved)
    return saved

def list_saved_products(db: Session, user_id: int) -> list[SavedProduct]:
    return (
        db.query(SavedProduct)
        .filter(SavedProduct.user_id == user_id)
        .order_by(SavedProduct.created_at.desc())
        .all()
    )

def unsave_product(db: Session, user_id: int, saved_id: int) -> bool:
    saved = (
        db.query(SavedProduct)
        .filter(SavedProduct.id == saved_id, SavedProduct.user_id == user_id)
        .first()
    )
    if not saved:
        return False
    db.delete(saved)
    db.commit()
    return True
