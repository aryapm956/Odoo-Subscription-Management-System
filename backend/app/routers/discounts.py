"""Discount rules router (admin-only write)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.auth import get_current_user, require_admin, require_staff_or_admin
from app.database import get_db

router = APIRouter(prefix="/discounts", tags=["discounts"])


class DiscountCreate(BaseModel):
    name: str
    type: str = "percentage"
    value: Decimal
    min_purchase: Optional[Decimal] = None
    min_quantity: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    usage_limit: Optional[int] = None
    applies_to: str = "subscription"
    product_id: Optional[int] = None
    subscription_id: Optional[int] = None


class DiscountUpdate(BaseModel):
    name: Optional[str] = None
    value: Optional[Decimal] = None
    min_purchase: Optional[Decimal] = None
    min_quantity: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    usage_limit: Optional[int] = None
    is_active: Optional[bool] = None


def discount_to_dict(d: models.DiscountRule) -> dict:
    return {
        "id": d.id,
        "name": d.name,
        "type": d.type.value,
        "value": float(d.value),
        "min_purchase": float(d.min_purchase) if d.min_purchase else None,
        "min_quantity": d.min_quantity,
        "start_date": d.start_date.isoformat() if d.start_date else None,
        "end_date": d.end_date.isoformat() if d.end_date else None,
        "usage_limit": d.usage_limit,
        "times_used": d.times_used,
        "applies_to": d.applies_to.value,
        "product_id": d.product_id,
        "subscription_id": d.subscription_id,
        "is_active": d.is_active,
    }


@router.get("")
def list_discounts(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_staff_or_admin),
):
    q = db.query(models.DiscountRule)
    total = q.count()
    items = q.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [discount_to_dict(d) for d in items],
    }


@router.post("", status_code=201)
def create_discount(
    data: DiscountCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    discount = models.DiscountRule(
        name=data.name,
        type=models.DiscountType(data.type),
        value=data.value,
        min_purchase=data.min_purchase,
        min_quantity=data.min_quantity,
        start_date=data.start_date,
        end_date=data.end_date,
        usage_limit=data.usage_limit,
        applies_to=models.DiscountAppliesTo(data.applies_to),
        product_id=data.product_id,
        subscription_id=data.subscription_id,
    )
    db.add(discount)
    db.commit()
    db.refresh(discount)
    return discount_to_dict(discount)


@router.get("/{discount_id}")
def get_discount(
    discount_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_staff_or_admin),
):
    d = db.query(models.DiscountRule).filter(models.DiscountRule.id == discount_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Discount not found")
    return discount_to_dict(d)


@router.put("/{discount_id}")
def update_discount(
    discount_id: int,
    data: DiscountUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    d = db.query(models.DiscountRule).filter(models.DiscountRule.id == discount_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="Discount not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(d, k, v)
    db.commit()
    db.refresh(d)
    return discount_to_dict(d)
