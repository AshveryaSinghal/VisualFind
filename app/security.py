"""
Auth primitives: password hashing, JWT access tokens, and password-reset
tokens. Kept in one small dependency-free-ish module so app/routers/auth.py
and app/deps.py both import from a single, easy-to-audit place.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(plain_password: str) -> str:
    return pwd_context.hash(plain_password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except ValueError:

        return False

def create_access_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)

class InvalidTokenError(Exception):
    pass

def decode_access_token(token: str) -> int:
    """Returns the user id encoded in the token, or raises InvalidTokenError."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        return int(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError, TypeError) as e:
        raise InvalidTokenError(str(e)) from e

def generate_password_reset_token() -> tuple[str, str, datetime]:
    """Returns (raw_token, token_hash, expires_at).

    The raw token is what goes in the emailed link; only its SHA-256 hash
    is persisted (see PasswordResetToken in app/database.py).
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_reset_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.password_reset_token_expire_minutes
    )
    return raw_token, token_hash, expires_at

def hash_reset_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
