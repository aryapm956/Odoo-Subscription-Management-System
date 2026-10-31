"""
Seed script for Brightloop SMS demo data.
Usage:
  python seed.py           # standard seed
  python seed.py --large   # + 5000 subscriptions, 20000+ invoices
"""
from __future__ import annotations

import sys
import random
import string
from datetime import date, timedelta, datetime
from decimal import Decimal

from dateutil.relativedelta import relativedelta

# Bootstrap DB
from app.database import engine, SessionLocal, Base, ensure_sqlite_schema
from app import models
from app.auth import hash_password
from app.billing import next_invoice_number, next_subscription_number, advance_date

Base.metadata.create_all(bind=engine)
ensure_sqlite_schema()
db = SessionLocal()

LARGE = "--large" in sys.argv
print(f"Seeding database... (large={LARGE})")


def normalize_next_billing(session, today):
    """Move seeded active subscriptions' next billing date to today or later."""
    active_subs = session.query(models.Subscription).filter(
        models.Subscription.status == models.SubscriptionStatus.active
    ).all()
    for sub in active_subs:
        if not sub.next_billing_date or sub.next_billing_date >= today:
            continue
        next_date = sub.next_billing_date
        guard = 0
        while next_date < today and guard < 1000:
            next_date = advance_date(next_date, sub.plan.billing_period)
            guard += 1
        sub.next_billing_date = next_date


def rnd_str(n=8):
    return ''.join(random.choices(string.ascii_lowercase, k=n))


def rnd_date_between(start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=random.randint(0, delta))


# ---------------------------------------------------------------------------
# Check if already seeded
# ---------------------------------------------------------------------------
if db.query(models.User).filter(models.User.email == "admin@brightloop.com").first():
    print("Database already seeded. Skipping standard seed.")
    if not LARGE:
        db.close()
        sys.exit(0)
    LARGE_ONLY = True
else:
    LARGE_ONLY = False

# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------
if not LARGE_ONLY:
    admin = models.User(
        name="Arya Admin",
        email="admin@brightloop.com",
        password_hash=hash_password("Admin@12345"),
        role=models.UserRole.admin,
    )
    staff = models.User(
        name="Sam Staff",
        email="staff@brightloop.com",
        password_hash=hash_password("Staff@12345"),
        role=models.UserRole.internal,
    )
    cust_user = models.User(
        name="Chris Customer",
        email="customer@brightloop.com",
        password_hash=hash_password("Customer@12345"),
        role=models.UserRole.customer,
    )
    db.add_all([admin, staff, cust_user])
    db.flush()

    # ---------------------------------------------------------------------------
    # Customers
    # ---------------------------------------------------------------------------
    COMPANY_NAMES = [
        "Acme Corp", "Globex Inc", "Initech", "Umbrella Ltd", "Stark Industries",
        "Wayne Enterprises", "Oscorp", "Cyberdyne Systems", "Weyland Corp", "InGen",
        "MomCorp", "Planet Express", "Sabre", "Dunder Mifflin", "Vandelay Industries",
        "Prestige Worldwide", "Stay Puft Corp", "Buy n Large", "Rekall", "Soylent Corp",
    ]
    FIRST_NAMES = ["Alice", "Bob", "Carol", "Dave", "Eve", "Frank", "Grace", "Hank", "Iris", "Jack",
                   "Kate", "Leo", "Mia", "Nina", "Oscar", "Pam", "Quinn", "Rita", "Sam", "Tara"]

    main_customer = models.Customer(
        user_id=cust_user.id,
        name="Chris Customer",
        email="customer@brightloop.com",
        phone="+91-9876543210",
        company="Customer Corp",
        address="123 Main St, Bangalore",
    )
    db.add(main_customer)
    db.flush()

    extra_customers = []
    for i, (fn, co) in enumerate(zip(FIRST_NAMES, COMPANY_NAMES)):
        c = models.Customer(
            name=f"{fn} {rnd_str(5).capitalize()}",
            email=f"{fn.lower()}.{rnd_str(4)}@{rnd_str(6)}.com",
            phone=f"+91-{random.randint(7000000000,9999999999)}",
            company=co,
            address=f"{random.randint(1,999)} {rnd_str(6).capitalize()} Road",
        )
        db.add(c)
        extra_customers.append(c)
    db.flush()
    all_customers = [main_customer] + extra_customers

    # ---------------------------------------------------------------------------
    # Taxes
    # ---------------------------------------------------------------------------
    gst18 = models.Tax(name="GST 18%", rate_percent=Decimal("18.00"), is_default=True, is_active=True)
    gst5 = models.Tax(name="GST 5%", rate_percent=Decimal("5.00"), is_default=False, is_active=True)
    db.add_all([gst18, gst5])
    db.flush()

    # ---------------------------------------------------------------------------
    # Products
    # ---------------------------------------------------------------------------
    products_data = [
        {
            "name": "Brightloop CRM",
            "type": models.ProductType.software,
            "sales_price": Decimal("2999.00"),
            "cost_price": Decimal("500.00"),
            "notes": "Core CRM platform",
            "variants": [
                ("Brand", "Odoo", Decimal("560.00")),
                ("Brand", "Custom", Decimal("0.00")),
            ],
        },
        {
            "name": "Analytics Suite",
            "type": models.ProductType.software,
            "sales_price": Decimal("1999.00"),
            "cost_price": Decimal("300.00"),
            "notes": "Advanced analytics and reporting",
            "variants": [],
        },
        {
            "name": "Support Add-on",
            "type": models.ProductType.addon,
            "sales_price": Decimal("499.00"),
            "cost_price": Decimal("50.00"),
            "notes": "Priority support package",
            "variants": [],
        },
        {
            "name": "Extra Seats Add-on",
            "type": models.ProductType.addon,
            "sales_price": Decimal("299.00"),
            "cost_price": Decimal("30.00"),
            "notes": "Per additional user seat",
            "variants": [],
        },
        {
            "name": "Data Storage Add-on",
            "type": models.ProductType.addon,
            "sales_price": Decimal("199.00"),
            "cost_price": Decimal("20.00"),
            "notes": "100GB additional storage",
            "variants": [],
        },
    ]

    products = {}
    for pd in products_data:
        p = models.Product(
            name=pd["name"],
            type=pd["type"],
            sales_price=pd["sales_price"],
            cost_price=pd["cost_price"],
            notes=pd["notes"],
        )
        db.add(p)
        db.flush()
        db.add(models.ProductTax(product_id=p.id, tax_id=gst18.id))
        variants = []
        for attr, val, extra in pd["variants"]:
            v = models.ProductVariant(product_id=p.id, attribute=attr, value=val, extra_price=extra)
            db.add(v)
            variants.append(v)
        db.flush()
        products[pd["name"]] = {"product": p, "variants": variants}

    crm = products["Brightloop CRM"]["product"]
    crm_odoo_variant = products["Brightloop CRM"]["variants"][0]  # Odoo +560
    analytics = products["Analytics Suite"]["product"]
    support = products["Support Add-on"]["product"]
    extra_seats = products["Extra Seats Add-on"]["product"]

    # ---------------------------------------------------------------------------
    # Plans
    # ---------------------------------------------------------------------------
    today = date.today()
    plans_data = [
        {
            "name": "Monthly Basic",
            "price": Decimal("2999.00"),
            "billing_period": models.BillingPeriod.monthly,
            "min_quantity": 1,
            "auto_close_on_end": False,
            "allow_early_close": True,
            "allow_pause": True,
            "allow_renew": True,
        },
        {
            "name": "Yearly Pro",
            "price": Decimal("29999.00"),
            "billing_period": models.BillingPeriod.yearly,
            "min_quantity": 1,
            "auto_close_on_end": True,
            "allow_early_close": False,
            "allow_pause": False,
            "allow_renew": True,
        },
        {
            "name": "Weekly Trial",
            "price": Decimal("799.00"),
            "billing_period": models.BillingPeriod.weekly,
            "min_quantity": 1,
            "start_date": today - timedelta(days=60),
            "end_date": today + timedelta(days=30),
            "auto_close_on_end": True,
            "allow_early_close": True,
            "allow_pause": True,
            "allow_renew": False,
        },
        {
            "name": "Daily Pilot",
            "price": Decimal("149.00"),
            "billing_period": models.BillingPeriod.daily,
            "min_quantity": 1,
            "auto_close_on_end": False,
            "allow_early_close": True,
            "allow_pause": True,
            "allow_renew": True,
        },
        {
            "name": "Enterprise Annual",
            "price": Decimal("99999.00"),
            "billing_period": models.BillingPeriod.yearly,
            "min_quantity": 5,
            "auto_close_on_end": False,
            "allow_early_close": False,
            "allow_pause": False,
            "allow_renew": True,
        },
    ]

    plans = {}
    for pd in plans_data:
        p = models.Plan(
            name=pd["name"],
            price=pd["price"],
            billing_period=pd["billing_period"],
            min_quantity=pd.get("min_quantity", 1),
            start_date=pd.get("start_date"),
            end_date=pd.get("end_date"),
            auto_close_on_end=pd.get("auto_close_on_end", False),
            allow_early_close=pd.get("allow_early_close", True),
            allow_pause=pd.get("allow_pause", True),
            allow_renew=pd.get("allow_renew", True),
        )
        db.add(p)
        plans[pd["name"]] = p
    db.flush()

    monthly_plan = plans["Monthly Basic"]
    yearly_plan = plans["Yearly Pro"]
    weekly_plan = plans["Weekly Trial"]
    daily_plan = plans["Daily Pilot"]

    # ---------------------------------------------------------------------------
    # Quotation Templates
    # ---------------------------------------------------------------------------
    template1 = models.QuotationTemplate(name="CRM Starter Pack", validity_days=30, plan_id=monthly_plan.id)
    db.add(template1)
    db.flush()
    db.add(models.QuotationTemplateLine(template_id=template1.id, product_id=crm.id, variant_id=crm_odoo_variant.id, quantity=1))
    db.add(models.QuotationTemplateLine(template_id=template1.id, product_id=support.id, quantity=1))

    template2 = models.QuotationTemplate(name="Yearly Pro Package", validity_days=14, plan_id=yearly_plan.id)
    db.add(template2)
    db.flush()
    db.add(models.QuotationTemplateLine(template_id=template2.id, product_id=crm.id, quantity=1))
    db.add(models.QuotationTemplateLine(template_id=template2.id, product_id=analytics.id, quantity=1))
    db.add(models.QuotationTemplateLine(template_id=template2.id, product_id=support.id, quantity=1))
    db.flush()

    # ---------------------------------------------------------------------------
    # Discount Rules
    # ---------------------------------------------------------------------------
    disc1 = models.DiscountRule(
        name="10% Bulk Seats (qty >= 10)",
        type=models.DiscountType.percentage,
        value=Decimal("10.00"),
        min_quantity=10,
        applies_to=models.DiscountAppliesTo.product,
        product_id=extra_seats.id,
        is_active=True,
    )
    disc2 = models.DiscountRule(
        name="Flat ₹500 for Yearly",
        type=models.DiscountType.fixed,
        value=Decimal("500.00"),
        applies_to=models.DiscountAppliesTo.subscription,
        plan_id=yearly_plan.id,
        is_active=True,
    )
    disc3 = models.DiscountRule(
        name="15% Launch Discount (EXPIRED)",
        type=models.DiscountType.percentage,
        value=Decimal("15.00"),
        start_date=today - timedelta(days=120),
        end_date=today - timedelta(days=30),
        applies_to=models.DiscountAppliesTo.subscription,
        is_active=True,
    )
    disc4 = models.DiscountRule(
        name="5% Limited Coupon (Usage Limit Reached)",
        type=models.DiscountType.percentage,
        value=Decimal("5.00"),
        usage_limit=5,
        times_used=5,
        applies_to=models.DiscountAppliesTo.subscription,
        is_active=True,
    )
    db.add_all([disc1, disc2, disc3, disc4])
    db.flush()

    # ---------------------------------------------------------------------------
    # Helper: create subscription + lines + invoices
    # ---------------------------------------------------------------------------
    def make_sub_number():
        count = db.query(models.Subscription).count()
        return f"SUB-{count + 1:05d}"

    def make_inv_number():
        count = db.query(models.Invoice).count()
        return f"INV-{count + 1:05d}"

    def create_subscription(
        customer, plan, status, start_date, expiry_date=None,
        paused=False, lines_data=None,
    ):
        sub = models.Subscription(
            number=make_sub_number(),
            customer_id=customer.id,
            plan_id=plan.id,
            start_date=start_date,
            expiry_date=expiry_date,
            payment_terms=random.choice(["Immediate", "Net 15", "Net 30"]),
            status=status,
            next_billing_date=start_date if status == models.SubscriptionStatus.active else None,
            paused=paused,
            created_by=admin.id,
        )
        db.add(sub)
        db.flush()

        if lines_data is None:
            lines_data = [{"product": crm, "variant": None, "qty": 1}]

        for ld in lines_data:
            p = ld["product"]
            v = ld.get("variant")
            qty = ld.get("qty", 1)
            unit_price = Decimal(str(p.sales_price))
            if v:
                unit_price += Decimal(str(v.extra_price))
            db.add(models.SubscriptionLine(
                subscription_id=sub.id,
                product_id=p.id,
                variant_id=v.id if v else None,
                quantity=qty,
                unit_price=unit_price,
                tax_id=gst18.id,
                amount=unit_price * qty,
            ))
        db.flush()
        return sub

    def create_invoice(sub, period_start, period_end_date, inv_status, pay_full=False, pay_partial=False):
        subtotal = sum(
            Decimal(str(l.unit_price)) * l.quantity
            for l in sub.lines
        )
        tax_total = (subtotal * Decimal("0.18")).quantize(Decimal("0.01"))
        total = subtotal + tax_total

        due_days = {"Immediate": 0, "Net 15": 15, "Net 30": 30}.get(sub.payment_terms, 0)
        issue_date = period_start
        due_date = issue_date + timedelta(days=due_days)

        inv = models.Invoice(
            number=make_inv_number(),
            subscription_id=sub.id,
            customer_id=sub.customer_id,
            billing_period_start=period_start,
            billing_period_end=period_end_date,
            issue_date=issue_date,
            due_date=due_date,
            status=inv_status,
            subtotal=subtotal,
            discount_total=Decimal("0.00"),
            tax_total=tax_total,
            total=total,
            amount_paid=Decimal("0.00"),
            balance_due=total,
        )

        if inv_status == models.InvoiceStatus.paid or pay_full:
            inv.amount_paid = total
            inv.balance_due = Decimal("0.00")
            inv.status = models.InvoiceStatus.paid
        elif pay_partial:
            partial = (total * Decimal("0.50")).quantize(Decimal("0.01"))
            inv.amount_paid = partial
            inv.balance_due = total - partial

        db.add(inv)
        db.flush()

        # Add lines
        for sl in sub.lines:
            line_gross = Decimal(str(sl.unit_price)) * sl.quantity
            line_tax = (line_gross * Decimal("0.18")).quantize(Decimal("0.01"))
            db.add(models.InvoiceLine(
                invoice_id=inv.id,
                description=sl.product.name if sl.product else "Service",
                product_id=sl.product_id,
                quantity=sl.quantity,
                unit_price=sl.unit_price,
                tax_rate=Decimal("18.00"),
                discount=Decimal("0.00"),
                amount=line_gross + line_tax,
            ))

        # Add payment record if paid
        if inv.status == models.InvoiceStatus.paid:
            db.add(models.Payment(
                invoice_id=inv.id,
                method=random.choice([m for m in models.PaymentMethod]),
                amount=inv.amount_paid,
                date=issue_date + timedelta(days=random.randint(0, 5)),
                recorded_by=staff.id,
            ))
        elif pay_partial:
            db.add(models.Payment(
                invoice_id=inv.id,
                method=models.PaymentMethod.bank_transfer,
                amount=inv.amount_paid,
                date=issue_date + timedelta(days=1),
                recorded_by=staff.id,
            ))

        db.flush()
        return inv

    # ---------------------------------------------------------------------------
    # Create representative subscriptions in all statuses
    # ---------------------------------------------------------------------------

    # 1. Active monthly subscription with some paid invoices
    sub_active_1 = create_subscription(
        main_customer, monthly_plan, models.SubscriptionStatus.active,
        today - timedelta(days=90), expiry_date=today + timedelta(days=275),
        lines_data=[
            {"product": crm, "variant": crm_odoo_variant, "qty": 1},
            {"product": support, "qty": 1},
        ]
    )
    # 3 months of invoices
    for i in range(3):
        p_start = (today - timedelta(days=90)) + relativedelta(months=i)
        p_end = p_start + relativedelta(months=1) - timedelta(days=1)
        pay_full = i < 2
        pay_partial = i == 2
        inv_status = models.InvoiceStatus.paid if pay_full else models.InvoiceStatus.confirmed
        create_invoice(sub_active_1, p_start, p_end, inv_status, pay_full=pay_full, pay_partial=pay_partial)
    sub_active_1.next_billing_date = today + relativedelta(months=1) - timedelta(days=90)
    db.flush()

    # 2. Active yearly subscription
    sub_active_2 = create_subscription(
        extra_customers[0], yearly_plan, models.SubscriptionStatus.active,
        today - timedelta(days=30), expiry_date=today + timedelta(days=335),
        lines_data=[
            {"product": crm, "qty": 1},
            {"product": analytics, "qty": 1},
        ]
    )
    create_invoice(sub_active_2, today - timedelta(days=30), today + timedelta(days=335),
                   models.InvoiceStatus.confirmed, pay_partial=True)

    # 3. Paused subscription
    sub_paused = create_subscription(
        extra_customers[1], monthly_plan, models.SubscriptionStatus.active,
        today - timedelta(days=60), paused=True,
        lines_data=[{"product": analytics, "qty": 1}]
    )
    create_invoice(sub_paused, today - timedelta(days=60), today - timedelta(days=31),
                   models.InvoiceStatus.paid, pay_full=True)

    # 4. Draft subscription
    create_subscription(
        extra_customers[2], monthly_plan, models.SubscriptionStatus.draft,
        today + timedelta(days=7),
    )

    # 5. Quotation
    create_subscription(
        extra_customers[3], weekly_plan, models.SubscriptionStatus.quotation,
        today + timedelta(days=3),
    )

    # 6. Confirmed subscription
    create_subscription(
        extra_customers[4], yearly_plan, models.SubscriptionStatus.confirmed,
        today,
    )

    # 7. Closed subscription with full history
    sub_closed = create_subscription(
        extra_customers[5], monthly_plan, models.SubscriptionStatus.closed,
        today - timedelta(days=180), expiry_date=today - timedelta(days=30),
        lines_data=[{"product": crm, "qty": 1}]
    )
    for i in range(5):
        p_start = (today - timedelta(days=180)) + relativedelta(months=i)
        p_end = p_start + relativedelta(months=1) - timedelta(days=1)
        create_invoice(sub_closed, p_start, p_end, models.InvoiceStatus.paid, pay_full=True)

    # 8. Overdue invoice scenario
    sub_overdue = create_subscription(
        extra_customers[6], monthly_plan, models.SubscriptionStatus.active,
        today - timedelta(days=45),
        lines_data=[{"product": crm, "qty": 1}]
    )
    # Confirmed invoice past due (overdue)
    overdue_inv = create_invoice(
        sub_overdue,
        today - timedelta(days=45),
        today - timedelta(days=16),
        models.InvoiceStatus.confirmed,
    )
    overdue_inv.due_date = today - timedelta(days=15)  # already overdue
    db.flush()

    # 9. Draft invoice scenario
    sub_draft_inv = create_subscription(
        extra_customers[15], monthly_plan, models.SubscriptionStatus.active,
        today - timedelta(days=5),
        lines_data=[{"product": analytics, "qty": 1}]
    )
    create_invoice(
        sub_draft_inv,
        today - timedelta(days=5),
        today + timedelta(days=24),
        models.InvoiceStatus.draft,
    )

    # 10. Cancelled invoice scenario
    sub_cancelled_inv = create_subscription(
        extra_customers[16], monthly_plan, models.SubscriptionStatus.active,
        today - timedelta(days=10),
        lines_data=[{"product": support, "qty": 1}]
    )
    cancelled_inv = create_invoice(
        sub_cancelled_inv,
        today - timedelta(days=10),
        today + timedelta(days=19),
        models.InvoiceStatus.confirmed,
    )
    cancelled_inv.status = models.InvoiceStatus.cancelled
    db.flush()

    # More active subs for remaining customers
    PLAN_LIST = [monthly_plan, yearly_plan, weekly_plan, daily_plan]
    PROD_LIST = [crm, analytics, support, extra_seats]
    for i, customer in enumerate(extra_customers[7:15]):
        plan = PLAN_LIST[i % len(PLAN_LIST)]
        start = today - timedelta(days=random.randint(10, 200))
        sub = create_subscription(
            customer, plan, models.SubscriptionStatus.active,
            start, expiry_date=start + timedelta(days=365),
            lines_data=[{"product": PROD_LIST[i % len(PROD_LIST)], "qty": 1}]
        )
        # Some paid invoices
        n_periods = random.randint(1, 4)
        for j in range(n_periods):
            if plan.billing_period == models.BillingPeriod.monthly:
                p_start = start + relativedelta(months=j)
            elif plan.billing_period == models.BillingPeriod.yearly:
                p_start = start + relativedelta(years=j)
            elif plan.billing_period == models.BillingPeriod.weekly:
                p_start = start + timedelta(weeks=j)
            else:
                p_start = start + timedelta(days=j)
            p_end = p_start + timedelta(days=29)
            if p_start < today:
                create_invoice(sub, p_start, p_end, models.InvoiceStatus.paid, pay_full=True)

    normalize_next_billing(db, today)
    db.commit()
    print("Standard seed complete.")
    print(f"  Admin: admin@brightloop.com / Admin@12345")
    print(f"  Staff: staff@brightloop.com / Staff@12345")
    print(f"  Customer: customer@brightloop.com / Customer@12345")

# ---------------------------------------------------------------------------
# Large seed
# ---------------------------------------------------------------------------
if LARGE:
    print("\nGenerating large dataset...")
    db2 = SessionLocal()

    admin = db2.query(models.User).filter(models.User.email == "admin@brightloop.com").first()
    all_customers_l = db2.query(models.Customer).all()
    all_plans_l = db2.query(models.Plan).all()
    all_products_l = db2.query(models.Product).all()
    gst18_l = db2.query(models.Tax).filter(models.Tax.is_default == True).first()

    def make_sub_num_l():
        count = db2.query(models.Subscription).count()
        return f"SUB-{count + 1:05d}"

    def make_inv_num_l():
        count = db2.query(models.Invoice).count()
        return f"INV-{count + 1:05d}"

    BATCH = 500
    total_subs = 5000
    total_created_subs = 0
    total_created_invs = 0
    today = date.today()

    for batch_start in range(0, total_subs, BATCH):
        subs_to_add = []
        lines_to_add = []
        invs_to_add = []
        inv_lines_to_add = []
        payments_to_add = []

        for _ in range(BATCH):
            customer = random.choice(all_customers_l)
            plan = random.choice(all_plans_l)
            product = random.choice(all_products_l)
            start = today - timedelta(days=random.randint(30, 730))
            status = random.choice([
                models.SubscriptionStatus.active,
                models.SubscriptionStatus.active,
                models.SubscriptionStatus.active,
                models.SubscriptionStatus.closed,
                models.SubscriptionStatus.confirmed,
            ])
            sub_count = db2.query(models.Subscription).count() + len(subs_to_add)
            sub = models.Subscription(
                number=f"SUB-{sub_count + 1:05d}",
                customer_id=customer.id,
                plan_id=plan.id,
                start_date=start,
                expiry_date=start + timedelta(days=365),
                payment_terms="Immediate",
                status=status,
                next_billing_date=start if status == models.SubscriptionStatus.active else None,
                paused=False,
                created_by=admin.id,
                created_at=datetime.utcnow(),
            )
            subs_to_add.append(sub)

        db2.add_all(subs_to_add)
        db2.flush()

        for sub in subs_to_add:
            product = random.choice(all_products_l)
            unit_price = Decimal(str(product.sales_price))
            line = models.SubscriptionLine(
                subscription_id=sub.id,
                product_id=product.id,
                quantity=1,
                unit_price=unit_price,
                tax_id=gst18_l.id if gst18_l else None,
                amount=unit_price,
            )
            lines_to_add.append(line)

        db2.add_all(lines_to_add)
        db2.flush()

        # Create invoices for active subs
        for sub, line in zip(subs_to_add, lines_to_add):
            if sub.status != models.SubscriptionStatus.active:
                continue
            n_months = random.randint(1, 6)
            for j in range(n_months):
                p_start = sub.start_date + relativedelta(months=j)
                if p_start >= today:
                    break
                p_end = p_start + relativedelta(months=1) - timedelta(days=1)
                subtotal = Decimal(str(line.unit_price))
                tax_total = (subtotal * Decimal("0.18")).quantize(Decimal("0.01"))
                total = subtotal + tax_total
                inv_status = models.InvoiceStatus.paid if random.random() < 0.7 else models.InvoiceStatus.confirmed
                amount_paid = total if inv_status == models.InvoiceStatus.paid else Decimal("0.00")
                balance_due = total - amount_paid

                inv_count = db2.query(models.Invoice).count() + len(invs_to_add)
                inv = models.Invoice(
                    number=f"INV-{inv_count + 1:05d}",
                    subscription_id=sub.id,
                    customer_id=sub.customer_id,
                    billing_period_start=p_start,
                    billing_period_end=p_end,
                    issue_date=p_start,
                    due_date=p_start,
                    status=inv_status,
                    subtotal=subtotal,
                    discount_total=Decimal("0.00"),
                    tax_total=tax_total,
                    total=total,
                    amount_paid=amount_paid,
                    balance_due=balance_due,
                )
                invs_to_add.append(inv)
                total_created_invs += 1

        db2.add_all(invs_to_add)
        db2.flush()

        # Payments for paid invoices
        for inv in invs_to_add:
            if inv.status == models.InvoiceStatus.paid:
                payments_to_add.append(models.Payment(
                    invoice_id=inv.id,
                    method=random.choice([m for m in models.PaymentMethod]),
                    amount=inv.amount_paid,
                    date=inv.issue_date,
                    recorded_by=admin.id,
                ))

        db2.add_all(payments_to_add)
        db2.commit()

        total_created_subs += BATCH
        print(f"  Progress: {total_created_subs}/{total_subs} subscriptions, {total_created_invs} invoices")

    db2.close()
    print(f"Large seed complete: {total_created_subs} subscriptions, {total_created_invs} invoices")

db.close()
print("\nSeeding done!")
