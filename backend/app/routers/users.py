"""Users/Staff management router (admin-only staff creation)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app import models
from app.auth import hash_password, validate_password, require_admin, get_current_user
from app.database import get_db

router = APIRouter(prefix="/users", tags=["users"])


class CreateStaffRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    role: str = "internal"

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("internal", "admin"):
            raise ValueError("Role must be 'internal' or 'admin'")
        return v


class UpdateUserRequest(BaseModel):
    name: str | None = None
    is_active: bool | None = None


@router.post("/staff", status_code=201)
def create_staff(
    data: CreateStaffRequest,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    errors = validate_password(data.password)
    if errors:
        raise HTTPException(status_code=422, detail={"errors": errors})

    existing = db.query(models.User).filter(func.lower(models.User.email) == data.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already in use")

    user = models.User(
        name=data.name,
        email=data.email,
        password_hash=hash_password(data.password),
        role=models.UserRole(data.role),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role.value}


@router.get("/staff")
def list_staff(
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    users = db.query(models.User).filter(
        models.User.role.in_([models.UserRole.internal, models.UserRole.admin])
    ).all()
    return [
        {"id": u.id, "name": u.name, "email": u.email, "role": u.role.value, "is_active": u.is_active}
        for u in users
    ]


@router.patch("/staff/{user_id}")
def update_staff(
    user_id: int,
    data: UpdateUserRequest,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if data.name is not None:
        user.name = data.name
    if data.is_active is not None:
        user.is_active = data.is_active
    db.commit()
    return {"id": user.id, "name": user.name, "email": user.email, "role": user.role.value, "is_active": user.is_active}
