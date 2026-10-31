"""Plans router (admin write)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import models
from app.auth import get_current_user, require_admin
from app.database import get_db

router = APIRouter(prefix="/plans", tags=["plans"])


class PlanCreate(BaseModel):
    name: str
    price: Decimal = Decimal("0.00")
    billing_period: str = "monthly"
    min_quantity: int = 1
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    auto_close_on_end: bool = False
    allow_early_close: bool = True
    allow_pause: bool = True
    allow_renew: bool = True


class PlanUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[Decimal] = None
    billing_period: Optional[str] = None
    min_quantity: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    auto_close_on_end: Optional[bool] = None
    allow_early_close: Optional[bool] = None
    allow_pause: Optional[bool] = None
    allow_renew: Optional[bool] = None
    is_active: Optional[bool] = None


def plan_to_dict(p: models.Plan) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "price": float(p.price),
        "billing_period": p.billing_period.value,
        "min_quantity": p.min_quantity,
        "start_date": p.start_date.isoformat() if p.start_date else None,
        "end_date": p.end_date.isoformat() if p.end_date else None,
        "auto_close_on_end": p.auto_close_on_end,
        "allow_early_close": p.allow_early_close,
        "allow_pause": p.allow_pause,
        "allow_renew": p.allow_renew,
        "is_active": p.is_active,
    }


@router.get("")
def list_plans(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    q = db.query(models.Plan)
    total = q.count()
    plans = q.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [plan_to_dict(p) for p in plans],
    }


@router.post("", status_code=201)
def create_plan(
    data: PlanCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    plan = models.Plan(
        name=data.name,
        price=data.price,
        billing_period=models.BillingPeriod(data.billing_period),
        min_quantity=data.min_quantity,
        start_date=data.start_date,
        end_date=data.end_date,
        auto_close_on_end=data.auto_close_on_end,
        allow_early_close=data.allow_early_close,
        allow_pause=data.allow_pause,
        allow_renew=data.allow_renew,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan_to_dict(plan)


@router.get("/{plan_id}")
def get_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    plan = db.query(models.Plan).filter(models.Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan_to_dict(plan)


@router.put("/{plan_id}")
def update_plan(
    plan_id: int,
    data: PlanUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    plan = db.query(models.Plan).filter(models.Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    for k, v in data.model_dump(exclude_none=True).items():
        if k == "billing_period":
            setattr(plan, k, models.BillingPeriod(v))
        else:
            setattr(plan, k, v)
    db.commit()
    db.refresh(plan)
    return plan_to_dict(plan)


@router.delete("/{plan_id}", status_code=204)
def delete_plan(
    plan_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    plan = db.query(models.Plan).filter(models.Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan.is_active = False
    db.commit()
