"""
Shared FastAPI dependencies for authentication.

get_current_user       -> 401s if there's no valid token. Use on every
                           route that returns or creates user-owned data
                           (search, history, analytics, profile).
get_current_user_optional -> returns None instead of 401ing when there's no
                           token. Not currently used by any route, but kept
                           available for any future public-but-personalized
                           endpoint.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import User, get_db
from app.security import InvalidTokenError, decode_access_token

_bearer_scheme = HTTPBearer(auto_error=False)

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials. Please sign in again.",
    headers={"WWW-Authenticate": "Bearer"},
)

def _resolve_user(
    credentials: HTTPAuthorizationCredentials | None, db: Session
) -> User | None:
    if credentials is None or not credentials.credentials:
        return None
    try:
        user_id = decode_access_token(credentials.credentials)
    except InvalidTokenError:
        raise _CREDENTIALS_ERROR
    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        raise _CREDENTIALS_ERROR
    return user

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    user = _resolve_user(credentials, db)
    if user is None:
        raise _CREDENTIALS_ERROR
    return user

def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User | None:
    return _resolve_user(credentials, db)
