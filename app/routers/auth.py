"""
HTTP layer for accounts: signup, login, logout, forgot/reset password, and
the profile (country/city/timezone). Same layering convention as the rest
of the app - validate here, business logic in app/security.py /
app/services/email_service.py, translate results/errors into responses.
"""

import logging
import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import PasswordResetToken, User, get_db
from app.deps import get_current_user
from app.models import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    ProfileUpdateRequest,
    ResetPasswordRequest,
    SignupRequest,
    TokenResponse,
    UserOut,
    UsernameAvailabilityResponse,
)
from app.rate_limit import limiter
from app.security import (
    create_access_token,
    generate_password_reset_token,
    hash_password,
    hash_reset_token,
    verify_password,
)
from app.services.email_service import send_password_reset_email
from app.services.username_service import generate_suggestions, is_username_taken

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

AUTH_RATE_LIMIT = "10/minute"

USERNAME_CHECK_RATE_LIMIT = "30/minute"

def _generic_forgot_password_response() -> dict:

    return {"detail": "If that email is registered, a password reset link has been sent."}

@router.get("/check-username", response_model=UsernameAvailabilityResponse)
@limiter.limit(USERNAME_CHECK_RATE_LIMIT)
def check_username(request: Request, username: str, db: Session = Depends(get_db)):
    username = username.strip()
    if not re.fullmatch(r"[a-zA-Z][a-zA-Z0-9_.]{2,29}", username):

        return UsernameAvailabilityResponse(username=username, available=False, suggestions=[])

    taken = is_username_taken(db, username)
    suggestions = generate_suggestions(db, username) if taken else []
    return UsernameAvailabilityResponse(username=username, available=not taken, suggestions=suggestions)

@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit(AUTH_RATE_LIMIT)
def signup(request: Request, body: SignupRequest, db: Session = Depends(get_db)):
    normalized_email = body.email.strip().lower()
    if db.query(User).filter(User.email == normalized_email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    if is_username_taken(db, body.username):
        raise HTTPException(status_code=409, detail="That username is already taken.")

    user = User(
        username=body.username,
        email=normalized_email,
        hashed_password=hash_password(body.password),
        full_name=(body.full_name or "").strip() or None,
        timezone="UTC",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))

@router.post("/login", response_model=TokenResponse)
@limiter.limit(AUTH_RATE_LIMIT)
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    identifier = body.identifier.strip().lower()

    user = (
        db.query(User)
        .filter((User.email == identifier) | (func.lower(User.username) == identifier))
        .first()
    )

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email/username or password.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated.")

    token = create_access_token(user.id)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))

@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(current_user: User = Depends(get_current_user)):
    """
    Access tokens are stateless JWTs, so there's no server-side session to
    destroy - the frontend just discards the token. This endpoint exists so
    the client has a real "logout" call to make (and a natural place to add
    server-side token revocation later, if that's ever needed).
    """
    return {"detail": "Logged out."}

@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.put("/me", response_model=UserOut)
def update_me(
    body: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if body.full_name is not None:
        current_user.full_name = body.full_name.strip() or None
    if body.country_code is not None:
        current_user.country_code = body.country_code.strip().upper() or None
    if body.country_name is not None:
        current_user.country_name = body.country_name.strip() or None
    if body.city is not None:
        current_user.city = body.city.strip() or None
    if body.timezone is not None and body.timezone.strip():
        current_user.timezone = body.timezone.strip()

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user

@router.post("/change-password", status_code=status.HTTP_200_OK)
@limiter.limit(AUTH_RATE_LIMIT)
def change_password(
    request: Request,
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")
    current_user.hashed_password = hash_password(body.new_password)
    db.add(current_user)
    db.commit()
    return {"detail": "Password changed."}

@router.post("/forgot-password", status_code=status.HTTP_200_OK)
@limiter.limit(AUTH_RATE_LIMIT)
def forgot_password(request: Request, body: ForgotPasswordRequest, db: Session = Depends(get_db)):
    normalized_email = body.email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()

    if user:
        raw_token, token_hash, expires_at = generate_password_reset_token()
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=token_hash,
                expires_at=expires_at,
            )
        )
        db.commit()
        try:
            send_password_reset_email(user.email, raw_token)
        except Exception:
            logger.exception("Password reset email dispatch failed for user_id=%s", user.id)

    return _generic_forgot_password_response()

@router.post("/reset-password", status_code=status.HTTP_200_OK)
@limiter.limit(AUTH_RATE_LIMIT)
def reset_password(request: Request, body: ResetPasswordRequest, db: Session = Depends(get_db)):
    token_hash = hash_reset_token(body.token)
    reset_row = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == token_hash)
        .first()
    )

    if not reset_row or reset_row.used:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has already been used.")

    expires_at = reset_row.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="This reset link has expired. Please request a new one.")

    user = db.query(User).filter(User.id == reset_row.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="This reset link is invalid or has already been used.")

    user.hashed_password = hash_password(body.new_password)
    reset_row.used = 1
    db.add(user)
    db.add(reset_row)
    db.commit()

    return {"detail": "Password has been reset. You can now log in with your new password."}
