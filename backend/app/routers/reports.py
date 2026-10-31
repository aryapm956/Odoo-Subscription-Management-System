"""Dashboard and reports router."""
from __future__ import annotations

import csv
import io
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from app import models
from app.auth import require_staff_or_admin
from app.database import get_db

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_staff_or_admin),
):
    today = date.today()

    # KPIs
    active_subs = db.query(func.count(models.Subscription.id)).filter(
        models.Subscription.status == models.SubscriptionStatus.active
    ).scalar()

    # MRR: sum active subscription line amounts and normalize to monthly (SQL aggregation)
    from decimal import Decimal

    mrr_rows = (
        db.query(
            models.Plan.billing_period,
            func.coalesce(func.sum(models.SubscriptionLine.amount), 0).label("total"),
        )
        .join(models.Subscription, models.Subscription.plan_id == models.Plan.id)
        .join(models.SubscriptionLine, models.SubscriptionLine.subscription_id == models.Subscription.id)
        .filter(models.Subscription.status == models.SubscriptionStatus.active)
        .group_by(models.Plan.billing_period)
        .all()
    )
    period_multipliers = {
        models.BillingPeriod.daily: Decimal("365") / Decimal("12"),
        models.BillingPeriod.weekly: Decimal("52") / Decimal("12"),
        models.BillingPeriod.monthly: Decimal("1"),
        models.BillingPeriod.yearly: Decimal("1") / Decimal("12"),
    }
    mrr = sum(
        Decimal(str(total)) * period_multipliers.get(period, Decimal("1"))
        for period, total in mrr_rows
    )

    # Total revenue collected (sum of payments, excluding cancelled invoices)
    total_revenue = (
        db.query(func.coalesce(func.sum(models.Payment.amount), 0))
        .join(models.Invoice, models.Payment.invoice_id == models.Invoice.id)
        .filter(models.Invoice.status != models.InvoiceStatus.cancelled)
        .scalar()
    )

    # Total outstanding (balance_due on confirmed invoices)
    total_outstanding = db.query(
        func.coalesce(func.sum(models.Invoice.balance_due), 0)
    ).filter(
        models.Invoice.status == models.InvoiceStatus.confirmed
    ).scalar()

    # Overdue invoices
    overdue_count = db.query(func.count(models.Invoice.id)).filter(
        models.Invoice.status == models.InvoiceStatus.confirmed,
        models.Invoice.balance_due > 0,
        models.Invoice.due_date < today,
    ).scalar()

    overdue_amount = db.query(
        func.coalesce(func.sum(models.Invoice.balance_due), 0)
    ).filter(
        models.Invoice.status == models.InvoiceStatus.confirmed,
        models.Invoice.balance_due > 0,
        models.Invoice.due_date < today,
    ).scalar()

    # Revenue by month (last 12 months)
    from sqlalchemy import extract
    revenue_by_month = (
        db.query(
            extract("year", models.Payment.date).label("year"),
            extract("month", models.Payment.date).label("month"),
            func.sum(models.Payment.amount).label("revenue"),
        )
        .join(models.Invoice, models.Payment.invoice_id == models.Invoice.id)
        .filter(
            models.Payment.date >= today - timedelta(days=365),
            models.Invoice.status != models.InvoiceStatus.cancelled,
        )
        .group_by("year", "month")
        .order_by("year", "month")
        .all()
    )

    # Subscriptions by status
    subs_by_status = (
        db.query(models.Subscription.status, func.count(models.Subscription.id))
        .group_by(models.Subscription.status)
        .all()
    )

    # Invoices: paid vs outstanding (last 12 months)
    invoices_summary = (
        db.query(
            extract("year", models.Invoice.issue_date).label("year"),
            extract("month", models.Invoice.issue_date).label("month"),
            func.sum(case((models.Invoice.status == models.InvoiceStatus.paid, models.Invoice.total), else_=0)).label("paid"),
            func.sum(case((models.Invoice.status == models.InvoiceStatus.confirmed, models.Invoice.balance_due), else_=0)).label("outstanding"),
        )
        .filter(models.Invoice.issue_date >= today - timedelta(days=365))
        .group_by("year", "month")
        .order_by("year", "month")
        .all()
    )

    return {
        "kpis": {
            "active_subscriptions": active_subs,
            "mrr": round(mrr, 2),
            "total_revenue": float(total_revenue),
            "total_outstanding": float(total_outstanding),
            "overdue_count": overdue_count,
            "overdue_amount": float(overdue_amount),
        },
        "revenue_by_month": [
            {"year": int(r.year), "month": int(r.month), "revenue": float(r.revenue)}
            for r in revenue_by_month
        ],
        "subscriptions_by_status": [
            {"status": s.value, "count": c}
            for s, c in subs_by_status
        ],
        "invoices_summary": [
            {
                "year": int(r.year),
                "month": int(r.month),
                "paid": float(r.paid),
                "outstanding": float(r.outstanding),
            }
            for r in invoices_summary
        ],
    }


@router.get("/active-subscriptions")
def active_subscriptions_report(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    plan_id: Optional[int] = None,
    customer_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_staff_or_admin),
):
    from sqlalchemy.orm import selectinload
    q = db.query(models.Subscription).options(
        selectinload(models.Subscription.customer),
        selectinload(models.Subscription.plan),
    ).filter(models.Subscription.status == models.SubscriptionStatus.active)
    if plan_id:
        q = q.filter(models.Subscription.plan_id == plan_id)
    if customer_id:
        q = q.filter(models.Subscription.customer_id == customer_id)
    total = q.count()
    subs = q.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "items": [
            {
                "id": s.id,
                "number": s.number,
                "customer": s.customer.name if s.customer else None,
                "plan": s.plan.name if s.plan else None,
                "billing_period": s.plan.billing_period.value if s.plan else None,
                "start_date": s.start_date.isoformat(),
                "expiry_date": s.expiry_date.isoformat() if s.expiry_date else None,
                "next_billing_date": s.next_billing_date.isoformat() if s.next_billing_date else None,
            }
            for s in subs
        ],
    }


@router.get("/revenue")
def revenue_report(
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_staff_or_admin),
):
    from sqlalchemy.orm import selectinload
    q = db.query(models.Payment).options(
        selectinload(models.Payment.invoice).selectinload(models.Invoice.customer)
    )
    if from_date:
        q = q.filter(models.Payment.date >= from_date)
    if to_date:
        q = q.filter(models.Payment.date <= to_date)
    total = q.count()
    payments = q.order_by(models.Payment.date.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    total_amount = db.query(func.sum(models.Payment.amount)).join(
        models.Invoice, models.Payment.invoice_id == models.Invoice.id
    ).filter(
        models.Invoice.status != models.InvoiceStatus.cancelled,
        *(([models.Payment.date >= from_date] if from_date else []) +
          ([models.Payment.date <= to_date] if to_date else []))
    ).scalar() or 0
    return {
        "total": total,
        "total_amount": float(total_amount),
        "items": [
            {
                "id": p.id,
                "invoice": p.invoice.number if p.invoice else None,
                "customer": p.invoice.customer.name if p.invoice and p.invoice.customer else None,
                "method": p.method.value,
                "amount": float(p.amount),
                "date": p.date.isoformat(),
                "note": p.note,
            }
            for p in payments
        ],
    }


@router.get("/overdue-invoices")
def overdue_invoices_report(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    customer_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_staff_or_admin),
):
    from sqlalchemy.orm import selectinload
    today = date.today()
    q = db.query(models.Invoice).options(
        selectinload(models.Invoice.customer),
        selectinload(models.Invoice.subscription),
    ).filter(
        models.Invoice.status == models.InvoiceStatus.confirmed,
        models.Invoice.balance_due > 0,
        models.Invoice.due_date < today,
    )
    if customer_id:
        q = q.filter(models.Invoice.customer_id == customer_id)
    total = q.count()
    invoices = q.order_by(models.Invoice.due_date).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    return {
        "total": total,
        "items": [
            {
                "id": inv.id,
                "number": inv.number,
                "customer": inv.customer.name if inv.customer else None,
                "subscription": inv.subscription.number if inv.subscription else None,
                "due_date": inv.due_date.isoformat(),
                "days_overdue": (today - inv.due_date).days,
                "balance_due": float(inv.balance_due),
                "total": float(inv.total),
            }
            for inv in invoices
        ],
    }


@router.get("/export/csv")
def export_csv(
    report: str = Query("invoices"),
    status: Optional[str] = None,
    from_date: Optional[date] = None,
    to_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_staff_or_admin),
):
    from sqlalchemy.orm import selectinload

    output = io.StringIO()
    writer = csv.writer(output)

    if report == "invoices":
        writer.writerow(["Number", "Customer", "Issue Date", "Due Date", "Status", "Total", "Paid", "Balance Due"])
        q = db.query(models.Invoice).options(selectinload(models.Invoice.customer))
        if status:
            q = q.filter(models.Invoice.status == models.InvoiceStatus(status))
        if from_date:
            q = q.filter(models.Invoice.issue_date >= from_date)
        if to_date:
            q = q.filter(models.Invoice.issue_date <= to_date)
        for inv in q.all():
            writer.writerow([
                inv.number,
                inv.customer.name if inv.customer else "",
                inv.issue_date.isoformat(),
                inv.due_date.isoformat(),
                inv.status.value,
                float(inv.total),
                float(inv.amount_paid),
                float(inv.balance_due),
            ])
    elif report == "subscriptions":
        writer.writerow(["Number", "Customer", "Plan", "Status", "Start Date", "Expiry Date", "Next Billing"])
        q = db.query(models.Subscription).options(
            selectinload(models.Subscription.customer),
            selectinload(models.Subscription.plan),
        )
        if status:
            q = q.filter(models.Subscription.status == models.SubscriptionStatus(status))
        for sub in q.all():
            writer.writerow([
                sub.number,
                sub.customer.name if sub.customer else "",
                sub.plan.name if sub.plan else "",
                sub.status.value,
                sub.start_date.isoformat(),
                sub.expiry_date.isoformat() if sub.expiry_date else "",
                sub.next_billing_date.isoformat() if sub.next_billing_date else "",
            ])
    elif report == "payments":
        writer.writerow(["Invoice", "Customer", "Method", "Amount", "Date", "Note"])
        q = db.query(models.Payment).options(
            selectinload(models.Payment.invoice).selectinload(models.Invoice.customer)
        )
        if from_date:
            q = q.filter(models.Payment.date >= from_date)
        if to_date:
            q = q.filter(models.Payment.date <= to_date)
        for p in q.all():
            writer.writerow([
                p.invoice.number if p.invoice else "",
                p.invoice.customer.name if p.invoice and p.invoice.customer else "",
                p.method.value,
                float(p.amount),
                p.date.isoformat(),
                p.note or "",
            ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={report}.csv"},
    )
