"""Authentication utilities: JWT, password hashing, validation."""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt as _bcrypt_lib
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app import models

settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)

ALGORITHM = "HS256"
PASSWORD_REGEX = re.compile(r'^(?=.*[a-z])(?=.*[A-Z])(?=.*[^a-zA-Z0-9]).{9,}$')


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_password(plain: str) -> str:
    return _bcrypt_lib.hashpw(plain.encode(), _bcrypt_lib.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _bcrypt_lib.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


def validate_password(plain: str) -> list[str]:
    """Return list of errors; empty list = valid."""
    errors: list[str] = []
    if len(plain) <= 8:
        errors.append("Password must be more than 8 characters.")
    if not re.search(r'[A-Z]', plain):
        errors.append("Password must contain at least one uppercase letter.")
    if not re.search(r'[a-z]', plain):
        errors.append("Password must contain at least one lowercase letter.")
    if not re.search(r'[^a-zA-Z0-9]', plain):
        errors.append("Password must contain at least one special character.")
    return errors


# ---------------------------------------------------------------------------
# JWT helpers
# ---------------------------------------------------------------------------

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ---------------------------------------------------------------------------
# Reset token helpers
# ---------------------------------------------------------------------------

def generate_reset_token() -> str:
    return secrets.token_urlsafe(48)


# ---------------------------------------------------------------------------
# Dependency: get current user
# ---------------------------------------------------------------------------

def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials)
    user_id: int = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    user = db.query(models.User).filter(models.User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def require_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    if current_user.role != models.UserRole.admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def require_staff_or_admin(current_user: models.User = Depends(get_current_user)) -> models.User:
    if current_user.role not in (models.UserRole.admin, models.UserRole.internal):
        raise HTTPException(status_code=403, detail="Staff or admin access required")
    return current_user


def require_customer(current_user: models.User = Depends(get_current_user)) -> models.User:
    if current_user.role != models.UserRole.customer:
        raise HTTPException(status_code=403, detail="Customer access required")
    return current_user
