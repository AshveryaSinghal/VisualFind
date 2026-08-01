"""Username availability + suggestion logic, used by both the live
/api/auth/check-username endpoint and the signup endpoint itself (signup
re-checks server-side so a race between two people claiming the same name
at the same instant is still rejected correctly).
"""

import random
import re

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import User

_SUFFIX_WORDS = ["ai", "pro", "hq", "official", "app", "dev", "shop", "labs"]

MAX_SUGGESTIONS = 5

def is_username_taken(db: Session, username: str) -> bool:
    """Case-insensitive uniqueness check - "Ashverya" and "ashverya" are the
    same handle."""
    return (
        db.query(User.id).filter(func.lower(User.username) == username.lower()).first()
        is not None
    )

def generate_suggestions(db: Session, username: str, count: int = MAX_SUGGESTIONS) -> list[str]:
    """Given a taken username, return `count` free alternatives close to
    what was typed: a few word-suffix variants, then random-number
    variants as a fallback so this always has something to offer.
    """
    base = re.sub(r"[^a-zA-Z0-9_.]", "", username).strip("._") or "user"
    candidates: list[str] = []
    seen: set[str] = set()

    def _try_add(candidate: str) -> None:
        candidate = candidate[:30]
        key = candidate.lower()
        if key in seen or key == username.lower():
            return
        seen.add(key)
        if not is_username_taken(db, candidate):
            candidates.append(candidate)

    for word in _SUFFIX_WORDS:
        if len(candidates) >= count:
            break
        _try_add(f"{base}_{word}")

    attempts = 0
    while len(candidates) < count and attempts < 25:
        attempts += 1
        _try_add(f"{base}{random.randint(1, 9999)}")

    return candidates[:count]
