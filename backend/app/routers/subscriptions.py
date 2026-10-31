"""Quotation templates and subscriptions router."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app import models
from app.auth import get_current_user, require_admin, require_staff_or_admin
from app.billing import next_subscription_number
from app.database import get_db

router = APIRouter(tags=["subscriptions"])

# Valid status transitions
VALID_TRANSITIONS = {
    models.SubscriptionStatus.draft: [models.SubscriptionStatus.quotation],
    models.SubscriptionStatus.quotation: [models.SubscriptionStatus.confirmed, models.SubscriptionStatus.draft],
    models.SubscriptionStatus.confirmed: [models.SubscriptionStatus.active, models.SubscriptionStatus.closed],
    models.SubscriptionStatus.active: [models.SubscriptionStatus.closed],
    models.SubscriptionStatus.closed: [],
}


# ---------------------------------------------------------------------------
# Quotation Template schemas & router
# ---------------------------------------------------------------------------

class TemplateLineCreate(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    quantity: int = 1


class TemplateCreate(BaseModel):
    name: str
    validity_days: int = 30
    plan_id: Optional[int] = None
    lines: List[TemplateLineCreate] = []


templates_router = APIRouter(prefix="/templates")


def template_to_dict(t: models.QuotationTemplate) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "validity_days": t.validity_days,
        "plan_id": t.plan_id,
        "plan_name": t.plan.name if t.plan else None,
        "lines": [
            {
                "id": l.id,
                "product_id": l.product_id,
                "product_name": l.product.name if l.product else None,
                "variant_id": l.variant_id,
                "quantity": l.quantity,
            }
            for l in t.lines
        ],
    }


@templates_router.get("")
def list_templates(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_staff_or_admin),
):
    templates = db.query(models.QuotationTemplate).options(
        selectinload(models.QuotationTemplate.lines).selectinload(models.QuotationTemplateLine.product),
        selectinload(models.QuotationTemplate.plan),
    ).all()
    return [template_to_dict(t) for t in templates]


@templates_router.post("", status_code=201)
def create_template(
    data: TemplateCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    template = models.QuotationTemplate(
        name=data.name,
        validity_days=data.validity_days,
        plan_id=data.plan_id,
    )
    db.add(template)
    db.flush()
    for l in data.lines:
        db.add(models.QuotationTemplateLine(
            template_id=template.id,
            product_id=l.product_id,
            variant_id=l.variant_id,
            quantity=l.quantity,
        ))
    db.commit()
    template = db.query(models.QuotationTemplate).options(
        selectinload(models.QuotationTemplate.lines).selectinload(models.QuotationTemplateLine.product),
        selectinload(models.QuotationTemplate.plan),
    ).filter(models.QuotationTemplate.id == template.id).first()
    return template_to_dict(template)


@templates_router.delete("/{template_id}", status_code=204)
def delete_template(
    template_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    t = db.query(models.QuotationTemplate).filter(models.QuotationTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    db.delete(t)
    db.commit()


# ---------------------------------------------------------------------------
# Subscription schemas & router
# ---------------------------------------------------------------------------

class SubLineCreate(BaseModel):
    product_id: int
    variant_id: Optional[int] = None
    quantity: int = 1
    unit_price: Decimal
    tax_id: Optional[int] = None


class SubscriptionCreate(BaseModel):
    customer_id: int
    plan_id: int
    start_date: date
    expiry_date: Optional[date] = None
    payment_terms: str = "Immediate"
    lines: List[SubLineCreate] = []
    notes: Optional[str] = None
    from_template_id: Optional[int] = None


class SubscriptionUpdate(BaseModel):
    expiry_date: Optional[date] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None


subscriptions_router = APIRouter(prefix="/subscriptions")


def sub_to_dict(s: models.Subscription, include_lines: bool = True) -> dict:
    d = {
        "id": s.id,
        "number": s.number,
        "customer_id": s.customer_id,
        "customer_name": s.customer.name if s.customer else None,
        "plan_id": s.plan_id,
        "plan_name": s.plan.name if s.plan else None,
        "billing_period": s.plan.billing_period.value if s.plan else None,
        "start_date": s.start_date.isoformat() if s.start_date else None,
        "expiry_date": s.expiry_date.isoformat() if s.expiry_date else None,
        "payment_terms": s.payment_terms,
        "status": s.status.value,
        "next_billing_date": s.next_billing_date.isoformat() if s.next_billing_date else None,
        "paused": s.paused,
        "notes": s.notes,
        "created_at": s.created_at.isoformat(),
        "allow_early_close": s.plan.allow_early_close if s.plan else True,
        "allow_pause": s.plan.allow_pause if s.plan else True,
        "allow_renew": s.plan.allow_renew if s.plan else True,
    }
    if include_lines:
        d["lines"] = [
            {
                "id": l.id,
                "product_id": l.product_id,
                "product_name": l.product.name if l.product else None,
                "variant_id": l.variant_id,
                "variant_label": f"{l.variant.attribute}: {l.variant.value}" if l.variant else None,
                "quantity": l.quantity,
                "unit_price": float(l.unit_price),
                "tax_id": l.tax_id,
                "tax_rate": float(l.tax.rate_percent) if l.tax else 0,
                "amount": float(l.amount),
            }
            for l in s.lines
        ]
    return d


def _load_sub(db: Session, sub_id: int) -> models.Subscription:
    return db.query(models.Subscription).options(
        selectinload(models.Subscription.lines).selectinload(models.SubscriptionLine.product),
        selectinload(models.Subscription.lines).selectinload(models.SubscriptionLine.variant),
        selectinload(models.Subscription.lines).selectinload(models.SubscriptionLine.tax),
        selectinload(models.Subscription.plan),
        selectinload(models.Subscription.customer),
    ).filter(models.Subscription.id == sub_id).first()


@subscriptions_router.get("")
def list_subscriptions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    customer_id: Optional[int] = None,
    plan_id: Optional[int] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    q = db.query(models.Subscription).options(
        selectinload(models.Subscription.plan),
        selectinload(models.Subscription.customer),
    )

    # Customer portal: only own subscriptions
    if current_user.role == models.UserRole.customer:
        my_customer = db.query(models.Customer).filter(
            models.Customer.user_id == current_user.id
        ).first()
        if not my_customer:
            return {"total": 0, "page": page, "page_size": page_size, "items": []}
        q = q.filter(models.Subscription.customer_id == my_customer.id)
    elif customer_id:
        q = q.filter(models.Subscription.customer_id == customer_id)

    if status:
        q = q.filter(models.Subscription.status == models.SubscriptionStatus(status))
    if plan_id:
        q = q.filter(models.Subscription.plan_id == plan_id)
    if search:
        q = q.filter(models.Subscription.number.ilike(f"%{search}%"))

    total = q.count()
    subs = q.order_by(models.Subscription.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [sub_to_dict(s, include_lines=False) for s in subs],
    }


@subscriptions_router.post("", status_code=201)
def create_subscription(
    data: SubscriptionCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_staff_or_admin),
):
    customer = db.query(models.Customer).filter(models.Customer.id == data.customer_id).first()
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    plan = db.query(models.Plan).filter(models.Plan.id == data.plan_id).first()
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    if not plan.is_active:
        raise HTTPException(status_code=400, detail="Plan is not active")
    today = date.today()
    if plan.start_date and today < plan.start_date:
        raise HTTPException(status_code=400, detail="Plan is not yet available")
    if plan.end_date and today > plan.end_date:
        raise HTTPException(status_code=400, detail="Plan availability has ended")

    lines_data = data.lines
    # If created from template, copy lines
    if data.from_template_id and not lines_data:
        template = db.query(models.QuotationTemplate).options(
            selectinload(models.QuotationTemplate.lines),
        ).filter(models.QuotationTemplate.id == data.from_template_id).first()
        if template:
            for tl in template.lines:
                product = db.query(models.Product).filter(models.Product.id == tl.product_id).first()
                unit_price = Decimal(str(product.sales_price))
                if tl.variant:
                    unit_price += Decimal(str(tl.variant.extra_price))
                lines_data.append(SubLineCreate(
                    product_id=tl.product_id,
                    variant_id=tl.variant_id,
                    quantity=tl.quantity,
                    unit_price=unit_price,
                ))

    # Validate min_quantity per line
    for l in lines_data:
        if l.quantity < plan.min_quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Minimum quantity for this plan is {plan.min_quantity}"
            )

    sub = models.Subscription(
        number=next_subscription_number(db),
        customer_id=data.customer_id,
        plan_id=data.plan_id,
        start_date=data.start_date,
        expiry_date=data.expiry_date,
        payment_terms=data.payment_terms,
        status=models.SubscriptionStatus.draft,
        next_billing_date=data.start_date,
        created_from_template_id=data.from_template_id,
        created_by=current_user.id,
        notes=data.notes,
    )
    db.add(sub)
    db.flush()

    default_tax = db.query(models.Tax).filter(
        models.Tax.is_active == True,
        models.Tax.is_default == True,
    ).first()

    for l in lines_data:
        product = db.query(models.Product).filter(models.Product.id == l.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail=f"Product {l.product_id} not found")
        variant = None
        if l.variant_id:
            variant = db.query(models.ProductVariant).filter(
                models.ProductVariant.id == l.variant_id
            ).first()
        unit_price = l.unit_price
        amount = Decimal(str(unit_price)) * l.quantity

        tax_id = l.tax_id
        if tax_id is None:
            product_tax = db.query(models.ProductTax).filter(
                models.ProductTax.product_id == l.product_id
            ).first()
            if product_tax:
                tax_id = product_tax.tax_id
            elif default_tax:
                tax_id = default_tax.id

        db.add(models.SubscriptionLine(
            subscription_id=sub.id,
            product_id=l.product_id,
            variant_id=l.variant_id,
            quantity=l.quantity,
            unit_price=unit_price,
            tax_id=tax_id,
            amount=amount,
        ))

    db.commit()
    sub = _load_sub(db, sub.id)
    return sub_to_dict(sub)


@subscriptions_router.get("/{sub_id}")
def get_subscription(
    sub_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    sub = _load_sub(db, sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    if current_user.role == models.UserRole.customer:
        my_customer = db.query(models.Customer).filter(
            models.Customer.user_id == current_user.id
        ).first()
        if not my_customer or sub.customer_id != my_customer.id:
            raise HTTPException(status_code=403, detail="Access denied")

    return sub_to_dict(sub)


@subscriptions_router.put("/{sub_id}")
def update_subscription(
    sub_id: int,
    data: SubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(require_staff_or_admin),
):
    sub = _load_sub(db, sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(sub, k, v)
    db.commit()
    sub = _load_sub(db, sub_id)
    return sub_to_dict(sub)


@subscriptions_router.post("/{sub_id}/transition")
def transition_subscription(
    sub_id: int,
    body: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Change subscription status. Enforces valid transitions and plan flags."""
    sub = _load_sub(db, sub_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    # Customer portal: only pause/close own subscription
    if current_user.role == models.UserRole.customer:
        my_customer = db.query(models.Customer).filter(
            models.Customer.user_id == current_user.id
        ).first()
        if not my_customer or sub.customer_id != my_customer.id:
            raise HTTPException(status_code=403, detail="Access denied")

    action = body.get("action", "")
    plan = sub.plan

    # Customers may only manage their own subscription lifecycle, not sales workflow states
    if current_user.role == models.UserRole.customer and action not in ("pause", "renew", "close", "closed"):
        raise HTTPException(
            status_code=403,
            detail="Customers can only pause, renew or close their subscriptions",
        )
    if action == "close":
        action = "closed"

    if action == "pause":
        if not plan.allow_pause:
            raise HTTPException(status_code=400, detail="This plan does not allow pausing")
        if sub.status != models.SubscriptionStatus.active:
            raise HTTPException(status_code=400, detail="Only active subscriptions can be paused")
        sub.paused = not sub.paused
        db.commit()
        sub = _load_sub(db, sub_id)
        return sub_to_dict(sub)

    if action == "renew":
        if not plan.allow_renew:
            raise HTTPException(status_code=400, detail="This plan does not allow renewal")
        if sub.status not in (models.SubscriptionStatus.active, models.SubscriptionStatus.closed):
            raise HTTPException(status_code=400, detail="Can only renew active or closed subscriptions")
        from app.billing import advance_date
        new_expiry = body.get("new_expiry_date")
        if new_expiry:
            sub.expiry_date = date.fromisoformat(new_expiry)
        else:
            sub.expiry_date = advance_date(sub.expiry_date or date.today(), plan.billing_period)
        if sub.status == models.SubscriptionStatus.closed:
            sub.status = models.SubscriptionStatus.active
        db.commit()
        sub = _load_sub(db, sub_id)
        return sub_to_dict(sub)

    # Status transition
    try:
        new_status = models.SubscriptionStatus(action)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unknown action: {action}")

    allowed = VALID_TRANSITIONS.get(sub.status, [])
    if new_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot transition from {sub.status.value} to {new_status.value}"
        )

    if new_status == models.SubscriptionStatus.closed and not plan.allow_early_close:
        if sub.expiry_date and date.today() < sub.expiry_date:
            raise HTTPException(status_code=400, detail="This plan does not allow early closing")

    if new_status == models.SubscriptionStatus.active:
        if not sub.next_billing_date:
            sub.next_billing_date = sub.start_date

    sub.status = new_status
    db.commit()
    sub = _load_sub(db, sub_id)
    return sub_to_dict(sub)


# Combined router
router = APIRouter()
router.include_router(templates_router)
router.include_router(subscriptions_router)
