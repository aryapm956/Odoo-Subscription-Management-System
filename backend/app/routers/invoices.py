"""Invoices router: CRUD, status transitions, send, print."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app import models
from app.auth import get_current_user, require_staff_or_admin
from app.billing import record_payment as do_record_payment, run_billing
from app.database import get_db
from app.email_service import send_invoice_email

router = APIRouter(prefix="/invoices", tags=["invoices"])


class RecordPaymentRequest(BaseModel):
    method: str
    amount: Decimal
    date: date
    note: Optional[str] = None


def invoice_to_dict(inv: models.Invoice, include_lines: bool = True) -> dict:
    d = {
        "id": inv.id,
        "number": inv.number,
        "subscription_id": inv.subscription_id,
        "subscription_number": inv.subscription.number if inv.subscription else None,
        "customer_id": inv.customer_id,
        "customer_name": inv.customer.name if inv.customer else None,
        "billing_period_start": inv.billing_period_start.isoformat(),
        "billing_period_end": inv.billing_period_end.isoformat(),
        "issue_date": inv.issue_date.isoformat(),
        "due_date": inv.due_date.isoformat(),
        "status": inv.status.value,
        "subtotal": float(inv.subtotal),
        "discount_total": float(inv.discount_total),
        "tax_total": float(inv.tax_total),
        "total": float(inv.total),
        "amount_paid": float(inv.amount_paid),
        "balance_due": float(inv.balance_due),
        "sent_at": inv.sent_at.isoformat() if inv.sent_at else None,
        "created_at": inv.created_at.isoformat(),
        "is_overdue": (
            inv.status == models.InvoiceStatus.confirmed
            and float(inv.balance_due) > 0
            and inv.due_date < date.today()
        ),
        "days_overdue": (
            (date.today() - inv.due_date).days
            if inv.status == models.InvoiceStatus.confirmed
            and float(inv.balance_due) > 0
            and inv.due_date < date.today()
            else 0
        ),
    }
    if include_lines:
        d["lines"] = [
            {
                "id": l.id,
                "description": l.description,
                "product_id": l.product_id,
                "quantity": l.quantity,
                "unit_price": float(l.unit_price),
                "tax_rate": float(l.tax_rate),
                "discount": float(l.discount),
                "amount": float(l.amount),
            }
            for l in inv.lines
        ]
        d["payments"] = [
            {
                "id": p.id,
                "method": p.method.value,
                "amount": float(p.amount),
                "date": p.date.isoformat(),
                "note": p.note,
                "created_at": p.created_at.isoformat(),
            }
            for p in inv.payments
        ]
    return d


def _load_invoice(db: Session, inv_id: int) -> models.Invoice:
    return (
        db.query(models.Invoice)
        .options(
            selectinload(models.Invoice.lines),
            selectinload(models.Invoice.payments),
            selectinload(models.Invoice.customer),
            selectinload(models.Invoice.subscription),
        )
        .filter(models.Invoice.id == inv_id)
        .first()
    )


@router.get("")
def list_invoices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    customer_id: Optional[int] = None,
    subscription_id: Optional[int] = None,
    overdue_only: bool = False,
    outstanding_only: bool = False,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    q = db.query(models.Invoice).options(
        selectinload(models.Invoice.customer),
        selectinload(models.Invoice.subscription),
    )

    if current_user.role == models.UserRole.customer:
        my_customer = db.query(models.Customer).filter(
            models.Customer.user_id == current_user.id
        ).first()
        if not my_customer:
            return {"total": 0, "page": page, "page_size": page_size, "items": []}
        q = q.filter(models.Invoice.customer_id == my_customer.id)
    elif customer_id:
        q = q.filter(models.Invoice.customer_id == customer_id)

    if subscription_id:
        q = q.filter(models.Invoice.subscription_id == subscription_id)
    if status:
        q = q.filter(models.Invoice.status == models.InvoiceStatus(status))
    if overdue_only:
        today = date.today()
        q = q.filter(
            models.Invoice.status == models.InvoiceStatus.confirmed,
            models.Invoice.balance_due > 0,
            models.Invoice.due_date < today,
        )
    if outstanding_only:
        q = q.filter(
            models.Invoice.status == models.InvoiceStatus.confirmed,
            models.Invoice.balance_due > 0,
        )
    if search:
        q = q.filter(models.Invoice.number.ilike(f"%{search}%"))

    total = q.count()
    invoices = q.order_by(models.Invoice.issue_date.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [invoice_to_dict(inv, include_lines=False) for inv in invoices],
    }


@router.get("/{invoice_id}")
def get_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    inv = _load_invoice(db, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    if current_user.role == models.UserRole.customer:
        my_customer = db.query(models.Customer).filter(
            models.Customer.user_id == current_user.id
        ).first()
        if not my_customer or inv.customer_id != my_customer.id:
            raise HTTPException(status_code=403, detail="Access denied")

    return invoice_to_dict(inv)


@router.post("/{invoice_id}/confirm")
def confirm_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_staff_or_admin),
):
    inv = _load_invoice(db, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status != models.InvoiceStatus.draft:
        raise HTTPException(status_code=400, detail="Only draft invoices can be confirmed")
    inv.status = models.InvoiceStatus.confirmed
    db.commit()
    return invoice_to_dict(inv)


@router.post("/{invoice_id}/cancel")
def cancel_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_staff_or_admin),
):
    inv = _load_invoice(db, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status == models.InvoiceStatus.paid:
        raise HTTPException(status_code=400, detail="Cannot cancel a paid invoice")
    if Decimal(str(inv.amount_paid)) > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot cancel an invoice that already has payments recorded",
        )
    inv.status = models.InvoiceStatus.cancelled
    db.commit()
    return invoice_to_dict(inv)


@router.post("/{invoice_id}/send")
def send_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_staff_or_admin),
):
    inv = _load_invoice(db, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if inv.status == models.InvoiceStatus.draft:
        raise HTTPException(status_code=400, detail="Confirm the invoice before sending")

    send_invoice_email(
        inv.customer.email if inv.customer else "",
        inv.customer.name if inv.customer else "Customer",
        inv.number,
    )
    inv.sent_at = datetime.now(timezone.utc)
    db.commit()
    return {"message": "Invoice sent", "sent_at": inv.sent_at.isoformat()}


@router.post("/{invoice_id}/payments")
def record_payment(
    invoice_id: int,
    data: RecordPaymentRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_staff_or_admin),
):
    inv = _load_invoice(db, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")

    try:
        payment = do_record_payment(
            db=db,
            invoice=inv,
            method=models.PaymentMethod(data.method),
            amount=data.amount,
            payment_date=data.date,
            note=data.note,
            recorded_by=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    inv = _load_invoice(db, invoice_id)
    return invoice_to_dict(inv)


@router.post("/billing-run")
def trigger_billing_run(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_staff_or_admin),
):
    """Manually trigger the billing run."""
    result = run_billing(db)
    return result
