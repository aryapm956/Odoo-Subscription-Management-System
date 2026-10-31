"""Payments router."""
from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, selectinload

from app import models
from app.auth import get_current_user
from app.database import get_db

router = APIRouter(prefix="/payments", tags=["payments"])


def payment_to_dict(p: models.Payment) -> dict:
    return {
        "id": p.id,
        "invoice_id": p.invoice_id,
        "invoice_number": p.invoice.number if p.invoice else None,
        "customer_name": p.invoice.customer.name if p.invoice and p.invoice.customer else None,
        "method": p.method.value,
        "amount": float(p.amount),
        "date": p.date.isoformat(),
        "note": p.note,
        "created_at": p.created_at.isoformat(),
    }


@router.get("")
def list_payments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    invoice_id: Optional[int] = None,
    method: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    q = db.query(models.Payment).options(
        selectinload(models.Payment.invoice).selectinload(models.Invoice.customer),
    )

    # Customer portal: only payments against their own invoices
    if current_user.role == models.UserRole.customer:
        my_customer = db.query(models.Customer).filter(
            models.Customer.user_id == current_user.id
        ).first()
        if not my_customer:
            return {"total": 0, "page": page, "page_size": page_size, "items": []}
        q = q.join(models.Invoice, models.Payment.invoice_id == models.Invoice.id).filter(
            models.Invoice.customer_id == my_customer.id
        )

    if invoice_id:
        q = q.filter(models.Payment.invoice_id == invoice_id)
    if method:
        q = q.filter(models.Payment.method == models.PaymentMethod(method))
    if from_date:
        q = q.filter(models.Payment.date >= from_date)
    if to_date:
        q = q.filter(models.Payment.date <= to_date)

    total = q.count()
    payments = q.order_by(models.Payment.date.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [payment_to_dict(p) for p in payments],
    }
