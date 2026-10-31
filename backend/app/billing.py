"""Core billing engine: invoice generation, tax calculation, discount application."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from dateutil.relativedelta import relativedelta

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from app import models

logger = logging.getLogger(__name__)

ZERO = Decimal("0.00")
TWO_PLACES = Decimal("0.01")


def _round(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Date arithmetic
# ---------------------------------------------------------------------------

def advance_date(d: date, period: models.BillingPeriod) -> date:
    if period == models.BillingPeriod.daily:
        return d + timedelta(days=1)
    if period == models.BillingPeriod.weekly:
        return d + timedelta(weeks=1)
    if period == models.BillingPeriod.monthly:
        return d + relativedelta(months=1)
    if period == models.BillingPeriod.yearly:
        return d + relativedelta(years=1)
    return d


def period_end(start: date, period: models.BillingPeriod) -> date:
    return advance_date(start, period) - timedelta(days=1)


# ---------------------------------------------------------------------------
# Auto-generate numbers
# ---------------------------------------------------------------------------

def next_subscription_number(db: Session) -> str:
    max_id = db.query(func.max(models.Subscription.id)).scalar() or 0
    return f"SUB-{max_id + 1:05d}"


def next_invoice_number(db: Session) -> str:
    max_id = db.query(func.max(models.Invoice.id)).scalar() or 0
    return f"INV-{max_id + 1:05d}"


# ---------------------------------------------------------------------------
# Discount helpers
# ---------------------------------------------------------------------------

def _discount_active(rule: models.DiscountRule, today: date) -> bool:
    if not rule.is_active:
        return False
    if rule.start_date and rule.start_date > today:
        return False
    if rule.end_date and rule.end_date < today:
        return False
    if rule.usage_limit is not None and rule.times_used >= rule.usage_limit:
        return False
    return True


def _apply_discount(base: Decimal, rule: models.DiscountRule) -> Decimal:
    if base <= ZERO:
        return ZERO
    if rule.type == models.DiscountType.percentage:
        return min(_round(base * Decimal(str(rule.value)) / Decimal("100")), base)
    return min(_round(Decimal(str(rule.value))), base)


# ---------------------------------------------------------------------------
# Invoice generation for a single subscription period
# ---------------------------------------------------------------------------

def _generate_invoice_for_period(
    db: Session,
    subscription: models.Subscription,
    period_start: date,
    today: date,
) -> models.Invoice | None:
    """Generate one invoice for subscription for period_start. Returns None if already exists."""
    # Idempotency check (unique constraint)
    existing = (
        db.query(models.Invoice)
        .filter(
            models.Invoice.subscription_id == subscription.id,
            models.Invoice.billing_period_start == period_start,
        )
        .first()
    )
    if existing:
        return None  # already billed

    plan = subscription.plan
    p_end = period_end(period_start, plan.billing_period)

    # Compute due date from payment_terms
    due_map = {"Immediate": 0, "Net 15": 15, "Net 30": 30, "Net 60": 60}
    due_days = due_map.get(subscription.payment_terms, 0)
    due_date = today + timedelta(days=due_days)

    # Get default tax
    default_tax = db.query(models.Tax).filter(
        models.Tax.is_active == True,
        models.Tax.is_default == True,
    ).first()

    # All discount rules that are active today and still have uses left
    all_rules = db.query(models.DiscountRule).filter(
        models.DiscountRule.is_active == True
    ).all()
    rules = [r for r in all_rules if _discount_active(r, today)]
    used_rule_ids: set[int] = set()

    # Build line records with product-level discounts applied first
    records = []
    total_qty = 0
    for sub_line in subscription.lines:
        unit_price = Decimal(str(sub_line.unit_price))
        qty = sub_line.quantity
        line_gross = _round(unit_price * qty)
        total_qty += qty

        product_rules = [
            r for r in rules
            if r.applies_to == models.DiscountAppliesTo.product
            and r.product_id == sub_line.product_id
            and (r.subscription_id is None or r.subscription_id == subscription.id)
            and (r.plan_id is None or r.plan_id == subscription.plan_id)
            and (r.min_purchase is None or line_gross >= r.min_purchase)
            and (r.min_quantity is None or qty >= r.min_quantity)
        ]
        product_discount = ZERO
        for rule in product_rules:
            product_discount += _apply_discount(line_gross - product_discount, rule)
            used_rule_ids.add(rule.id)
        product_discount = min(product_discount, line_gross)

        tax = sub_line.tax or default_tax
        tax_rate = Decimal(str(tax.rate_percent)) if tax else ZERO

        records.append({
            "sub_line": sub_line,
            "unit_price": unit_price,
            "qty": qty,
            "gross": line_gross,
            "product_discount": product_discount,
            "base": _round(line_gross - product_discount),
            "tax": tax,
            "tax_rate": tax_rate,
        })

    subtotal = _round(sum((r["gross"] for r in records), ZERO))
    product_discount_total = _round(sum((r["product_discount"] for r in records), ZERO))
    after_product = _round(subtotal - product_discount_total)

    # Subscription-level discounts apply once per invoice
    subscription_rules = [
        r for r in rules
        if r.applies_to == models.DiscountAppliesTo.subscription
        and (r.subscription_id is None or r.subscription_id == subscription.id)
        and (r.plan_id is None or r.plan_id == subscription.plan_id)
        and (r.min_purchase is None or subtotal >= r.min_purchase)
        and (r.min_quantity is None or total_qty >= r.min_quantity)
    ]
    subscription_discount = ZERO
    for rule in subscription_rules:
        remaining_base = _round(after_product - subscription_discount)
        if remaining_base <= ZERO:
            break
        subscription_discount += _apply_discount(remaining_base, rule)
        used_rule_ids.add(rule.id)
    subscription_discount = min(_round(subscription_discount), after_product)

    # Distribute subscription discount proportionally across line bases
    if after_product > ZERO and subscription_discount > ZERO:
        allocated = ZERO
        for idx, rec in enumerate(records):
            if idx == len(records) - 1:
                share = _round(subscription_discount - allocated)
            else:
                share = _round(subscription_discount * rec["base"] / after_product)
                allocated += share
            rec["base"] = max(_round(rec["base"] - share), ZERO)
            rec["sub_discount"] = share
    for rec in records:
        rec.setdefault("sub_discount", ZERO)

    invoice_lines = []
    discount_total = ZERO
    tax_total = ZERO
    for rec in records:
        sub_line = rec["sub_line"]
        taxable = rec["base"]
        line_tax = _round(taxable * rec["tax_rate"] / Decimal("100"))
        line_amount = _round(taxable + line_tax)
        line_discount = _round(rec["product_discount"] + rec["sub_discount"])

        product = sub_line.product
        variant = sub_line.variant
        desc = product.name if product else "Service"
        if variant:
            desc += f" ({variant.attribute}: {variant.value})"

        invoice_lines.append(models.InvoiceLine(
            description=desc,
            product_id=sub_line.product_id,
            variant_id=sub_line.variant_id,
            quantity=rec["qty"],
            unit_price=rec["unit_price"],
            tax_id=rec["tax"].id if rec["tax"] else None,
            tax_rate=rec["tax_rate"],
            discount=line_discount,
            amount=line_amount,
        ))
        discount_total += line_discount
        tax_total += line_tax

    subtotal = _round(subtotal)
    discount_total = _round(discount_total)
    tax_total = _round(tax_total)
    discount_total = min(discount_total, subtotal)
    total = _round(subtotal - discount_total + tax_total)
    total = max(total, ZERO)  # never negative

    if total <= ZERO:
        logger.info(
            "Skipping zero-total invoice for subscription %s period %s",
            subscription.number,
            period_start,
        )
        return None

    # Each discount rule counts once per invoice it is applied to
    for rule in rules:
        if rule.id in used_rule_ids:
            rule.times_used += 1

    invoice = models.Invoice(
        number=next_invoice_number(db),
        subscription_id=subscription.id,
        customer_id=subscription.customer_id,
        billing_period_start=period_start,
        billing_period_end=p_end,
        issue_date=today,
        due_date=due_date,
        status=models.InvoiceStatus.draft,
        subtotal=subtotal,
        discount_total=discount_total,
        tax_total=tax_total,
        total=total,
        amount_paid=ZERO,
        balance_due=total,
    )
    invoice.lines = invoice_lines
    db.add(invoice)
    db.flush()  # assign id/number before the next invoice in this batch
    return invoice


# ---------------------------------------------------------------------------
# Main billing run
# ---------------------------------------------------------------------------

def run_billing(db: Session, today: date | None = None) -> dict:
    """
    Run the billing cycle:
    1. Find all active, non-paused subs with next_billing_date <= today
    2. Generate invoices (idempotent, catch-up loop)
    3. Advance next_billing_date
    4. Auto-close subscriptions past their end date when plan.auto_close_on_end
    Returns summary dict.
    """
    today = today or date.today()
    created = 0
    skipped = 0
    failed = 0
    closed = 0

    # --- Step 1: auto-close subs ---
    subs_to_close = (
        db.query(models.Subscription)
        .join(models.Plan)
        .filter(
            models.Subscription.status == models.SubscriptionStatus.active,
            models.Plan.auto_close_on_end == True,
            models.Subscription.expiry_date != None,
            models.Subscription.expiry_date < today,
        )
        .all()
    )
    for sub in subs_to_close:
        sub.status = models.SubscriptionStatus.closed
        closed += 1
    if subs_to_close:
        db.commit()

    # --- Step 2: bill due subscriptions ---
    due_subs = (
        db.query(models.Subscription)
        .options(
            selectinload(models.Subscription.lines).selectinload(models.SubscriptionLine.product),
            selectinload(models.Subscription.lines).selectinload(models.SubscriptionLine.variant),
            selectinload(models.Subscription.lines).selectinload(models.SubscriptionLine.tax),
            selectinload(models.Subscription.plan),
        )
        .filter(
            models.Subscription.status == models.SubscriptionStatus.active,
            models.Subscription.paused == False,
            models.Subscription.next_billing_date != None,
            models.Subscription.next_billing_date <= today,
        )
        .all()
    )

    for sub in due_subs:
        sub_number = sub.number
        try:
            period_start = sub.next_billing_date
            periods_billed = 0

            # Catch-up loop: bill all missed periods
            while period_start <= today:
                invoice = _generate_invoice_for_period(db, sub, period_start, today)
                if invoice is None:
                    skipped += 1
                else:
                    created += 1
                period_start = advance_date(period_start, sub.plan.billing_period)
                periods_billed += 1
                if periods_billed > 1000:  # safety cap
                    break

            sub.next_billing_date = period_start
            db.commit()
        except Exception as exc:
            logger.error("Billing failed for subscription %s: %s", sub_number, exc)
            db.rollback()
            failed += 1

    return {
        "created": created,
        "skipped": skipped,
        "failed": failed,
        "closed": closed,
        "billing_date": today.isoformat(),
    }


# ---------------------------------------------------------------------------
# Payment recording
# ---------------------------------------------------------------------------

def record_payment(
    db: Session,
    invoice: models.Invoice,
    method: models.PaymentMethod,
    amount: Decimal,
    payment_date: date,
    note: str | None,
    recorded_by: int | None,
) -> models.Payment:
    if invoice.status == models.InvoiceStatus.paid:
        raise ValueError("Invoice is already fully paid")
    if invoice.status == models.InvoiceStatus.cancelled:
        raise ValueError("Cannot pay a cancelled invoice")
    if invoice.status == models.InvoiceStatus.draft:
        raise ValueError("Confirm the invoice before recording payment")

    balance = Decimal(str(invoice.balance_due))
    amount = _round(amount)
    if amount <= ZERO:
        raise ValueError("Payment amount must be positive")
    if amount > balance:
        raise ValueError(f"Payment amount {amount} exceeds balance {balance}")

    payment = models.Payment(
        invoice_id=invoice.id,
        method=method,
        amount=amount,
        date=payment_date,
        note=note,
        recorded_by=recorded_by,
    )
    db.add(payment)

    invoice.amount_paid = _round(Decimal(str(invoice.amount_paid)) + amount)
    invoice.balance_due = _round(Decimal(str(invoice.balance_due)) - amount)
    if invoice.balance_due <= ZERO:
        invoice.balance_due = ZERO
        invoice.status = models.InvoiceStatus.paid

    db.commit()
    db.refresh(payment)
    return payment
