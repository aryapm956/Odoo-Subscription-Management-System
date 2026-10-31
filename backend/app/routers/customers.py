"""Customers router."""
from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app import models
from app.auth import get_current_user, require_staff_or_admin
from app.database import get_db

router = APIRouter(prefix="/customers", tags=["customers"])


class CustomerCreate(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    company: Optional[str] = None
    address: Optional[str] = None


class CustomerUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    address: Optional[str] = None


def customer_to_dict(c: models.Customer) -> dict:
    return {
        "id": c.id,
        "user_id": c.user_id,
        "name": c.name,
        "email": c.email,
        "phone": c.phone,
        "company": c.company,
        "address": c.address,
        "created_at": c.created_at.isoformat(),
    }


@router.get("")
def list_customers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_staff_or_admin),
):
    q = db.query(models.Customer)
    if search:
        like = f"%{search}%"
        q = q.filter(
            (models.Customer.name.ilike(like)) |
            (models.Customer.email.ilike(like)) |
            (models.Customer.company.ilike(like))
        )
    total = q.count()
    customers = q.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [customer_to_dict(c) for c in customers],
    }


@router.post("", status_code=201)
def create_customer(
    data: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_staff_or_admin),
):
    customer = models.Customer(**data.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer_to_dict(customer)


@router.get("/{customer_id}")
def get_customer(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    # Ownership check for customer role
    if current_user.role == models.UserRole.customer:
        my_customer = db.query(models.Customer).filter(
            models.Customer.user_id == current_user.id
        ).first()
        if not my_customer or my_customer.id != customer_id:
            raise HTTPException(status_code=403, detail="Access denied")

    return customer_to_dict(customer)


@router.put("/{customer_id}")
def update_customer(
    customer_id: int,
    data: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_staff_or_admin),
):
    customer = db.query(models.Customer).filter(models.Customer.id == customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(customer, k, v)
    db.commit()
    db.refresh(customer)
    return customer_to_dict(customer)
