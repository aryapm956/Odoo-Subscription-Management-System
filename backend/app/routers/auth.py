"""Auth router: signup, login, password reset, dev outbox."""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.auth import (
    hash_password, verify_password, validate_password,
    create_access_token, generate_reset_token, get_current_user,
)
from app.config import get_settings
from app.database import get_db
from app.email_service import send_password_reset, get_outbox

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SignupRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()


class ForgotPasswordRequest(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str
    user_id: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/signup", response_model=TokenResponse, status_code=201)
def signup(data: SignupRequest, db: Session = Depends(get_db)):
    # Password validation
    errors = validate_password(data.password)
    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})

    # Unique email check
    existing = db.query(models.User).filter(func.lower(models.User.email) == data.email).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists.",
        )

    user = models.User(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        role=models.UserRole.customer,
    )
    db.add(user)
    db.flush()

    # Create customer profile
    customer = models.Customer(
        user_id=user.id,
        name=data.name,
        email=data.email,
    )
    db.add(customer)
    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return TokenResponse(
        access_token=token,
        role=user.role.value,
        name=user.name,
        user_id=user.id,
    )


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(func.lower(models.User.email) == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is inactive")

    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return TokenResponse(
        access_token=token,
        role=user.role.value,
        name=user.name,
        user_id=user.id,
    )


@router.post("/forgot-password", status_code=200)
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(func.lower(models.User.email) == data.email).first()
    # Always return 200 - don't reveal whether email exists
    if user and user.is_active:
        # Invalidate existing tokens
        db.query(models.PasswordResetToken).filter(
            models.PasswordResetToken.user_id == user.id,
            models.PasswordResetToken.used == False,
        ).update({"used": True})

        raw_token = generate_reset_token()
        expires = datetime.now(timezone.utc) + timedelta(
            minutes=settings.reset_token_expire_minutes
        )
        reset_record = models.PasswordResetToken(
            user_id=user.id,
            token=raw_token,
            expires_at=expires,
        )
        db.add(reset_record)
        db.commit()

        reset_url = f"{settings.frontend_url}/#/reset-password?token={raw_token}"
        send_password_reset(user.email, reset_url, user.name)

    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password", status_code=200)
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    record = (
        db.query(models.PasswordResetToken)
        .filter(
            models.PasswordResetToken.token == data.token,
            models.PasswordResetToken.used == False,
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    if record.expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset token has expired")

    errors = validate_password(data.password)
    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})

    user = db.query(models.User).filter(models.User.id == record.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    user.password_hash = hash_password(data.password)
    record.used = True
    db.commit()
    return {"message": "Password reset successfully"}


@router.get("/me")
def get_me(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    customer = db.query(models.Customer).filter(
        models.Customer.user_id == current_user.id
    ).first()
    return {
        "id": current_user.id,
        "name": current_user.name,
        "email": current_user.email,
        "role": current_user.role.value,
        "is_active": current_user.is_active,
        "customer_id": customer.id if customer else None,
    }


@router.get("/dev/outbox")
def dev_outbox():
    """Dev endpoint: see simulated emails (when SMTP not configured)."""
    return get_outbox()
