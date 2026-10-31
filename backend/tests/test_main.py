"""pytest tests for Brightloop SMS."""
from __future__ import annotations

import pytest
from datetime import date, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.database import Base, get_db
from app import models
from app.auth import hash_password

# ---------------------------------------------------------------------------
# Test DB setup
# ---------------------------------------------------------------------------

TEST_DB_URL = "sqlite:///./test_brightloop.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestSession()
    yield session
    session.close()


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_user(db, email, password, role, name="Test User"):
    user = models.User(
        name=name, email=email, password_hash=hash_password(password), role=role
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_customer_profile(db, user):
    c = models.Customer(user_id=user.id, name=user.name, email=user.email)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def create_tax(db):
    tax = models.Tax(name="GST 18%", rate_percent=Decimal("18.00"), is_default=True)
    db.add(tax)
    db.commit()
    db.refresh(tax)
    return tax


def create_product(db):
    p = models.Product(name="CRM", type=models.ProductType.software,
                       sales_price=Decimal("1000.00"), cost_price=Decimal("100.00"))
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def create_plan(db, **kwargs):
    defaults = dict(
        name="Monthly Plan",
        price=Decimal("1000.00"),
        billing_period=models.BillingPeriod.monthly,
        min_quantity=1,
        allow_early_close=True,
        allow_pause=True,
        allow_renew=True,
        auto_close_on_end=False,
    )
    defaults.update(kwargs)
    p = models.Plan(**defaults)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def create_subscription(db, customer, plan, status=models.SubscriptionStatus.draft, lines=None):
    count = db.query(models.Subscription).count()
    sub = models.Subscription(
        number=f"SUB-{count+1:05d}",
        customer_id=customer.id,
        plan_id=plan.id,
        start_date=date.today(),
        payment_terms="Immediate",
        status=status,
        next_billing_date=date.today() if status == models.SubscriptionStatus.active else None,
    )
    db.add(sub)
    db.flush()
    if lines:
        for ld in lines:
            db.add(models.SubscriptionLine(
                subscription_id=sub.id,
                product_id=ld["product_id"],
                quantity=ld.get("qty", 1),
                unit_price=ld["unit_price"],
                tax_id=ld.get("tax_id"),
                amount=ld["unit_price"] * ld.get("qty", 1),
            ))
    db.commit()
    db.refresh(sub)
    return sub


# ===========================================================================
# TESTS
# ===========================================================================

# ---------------------------------------------------------------------------
# 1. Password rules
# ---------------------------------------------------------------------------

class TestPasswordRules:
    def test_password_too_short(self, client):
        r = client.post("/api/auth/signup", json={
            "name": "Test", "email": "a@test.com", "password": "Ab!2345"
        })
        assert r.status_code == 422

    def test_password_no_uppercase(self, client):
        r = client.post("/api/auth/signup", json={
            "name": "Test", "email": "a@test.com", "password": "abc!defgh1"
        })
        assert r.status_code == 422

    def test_password_no_lowercase(self, client):
        r = client.post("/api/auth/signup", json={
            "name": "Test", "email": "a@test.com", "password": "ABC!DEFGH1"
        })
        assert r.status_code == 422

    def test_password_no_special(self, client):
        r = client.post("/api/auth/signup", json={
            "name": "Test", "email": "a@test.com", "password": "Abcdefgh12"
        })
        assert r.status_code == 422

    def test_valid_password(self, client):
        r = client.post("/api/auth/signup", json={
            "name": "Test", "email": "valid@test.com", "password": "Valid@12345"
        })
        assert r.status_code == 201

    def test_exactly_8_chars_fails(self, client):
        r = client.post("/api/auth/signup", json={
            "name": "Test", "email": "b@test.com", "password": "Ab!45678"
        })
        assert r.status_code == 422

    def test_9_chars_ok(self, client):
        r = client.post("/api/auth/signup", json={
            "name": "Test", "email": "c@test.com", "password": "Ab!456789"
        })
        assert r.status_code == 201


# ---------------------------------------------------------------------------
# 2. Duplicate email
# ---------------------------------------------------------------------------

class TestDuplicateEmail:
    def test_duplicate_email_rejected(self, client):
        data = {"name": "Test", "email": "dup@test.com", "password": "Valid@12345"}
        r1 = client.post("/api/auth/signup", json=data)
        assert r1.status_code == 201
        r2 = client.post("/api/auth/signup", json=data)
        assert r2.status_code == 409

    def test_case_insensitive_email(self, client):
        client.post("/api/auth/signup", json={
            "name": "Test", "email": "DUP2@test.com", "password": "Valid@12345"
        })
        r = client.post("/api/auth/signup", json={
            "name": "Test", "email": "dup2@TEST.COM", "password": "Valid@12345"
        })
        assert r.status_code == 409


# ---------------------------------------------------------------------------
# 3. RBAC: customer cannot see others' data
# ---------------------------------------------------------------------------

class TestRBAC:
    def test_customer_cannot_see_other_customer_subscription(self, client, db):
        # Create two customers
        u1 = create_user(db, "c1@test.com", "Valid@12345", models.UserRole.customer, "C1")
        c1 = create_customer_profile(db, u1)
        u2 = create_user(db, "c2@test.com", "Valid@12345", models.UserRole.customer, "C2")
        c2 = create_customer_profile(db, u2)

        plan = create_plan(db)
        sub = create_subscription(db, c2, plan, models.SubscriptionStatus.active)

        token1 = login(client, "c1@test.com", "Valid@12345")
        r = client.get(f"/api/subscriptions/{sub.id}", headers=auth_headers(token1))
        assert r.status_code == 403

    def test_customer_cannot_create_discount(self, client, db):
        u = create_user(db, "cust@test.com", "Valid@12345", models.UserRole.customer)
        token = login(client, "cust@test.com", "Valid@12345")
        r = client.post("/api/discounts", json={
            "name": "Test", "type": "percentage", "value": 10, "applies_to": "subscription"
        }, headers=auth_headers(token))
        assert r.status_code == 403

    def test_staff_cannot_create_discount(self, client, db):
        u = create_user(db, "staff@test.com", "Valid@12345", models.UserRole.internal)
        token = login(client, "staff@test.com", "Valid@12345")
        r = client.post("/api/discounts", json={
            "name": "Test", "type": "percentage", "value": 10, "applies_to": "subscription"
        }, headers=auth_headers(token))
        assert r.status_code == 403

    def test_staff_cannot_create_product(self, client, db):
        u = create_user(db, "staff2@test.com", "Valid@12345", models.UserRole.internal)
        token = login(client, "staff2@test.com", "Valid@12345")
        r = client.post("/api/products", json={
            "name": "Test Product", "type": "software", "sales_price": 100, "cost_price": 10
        }, headers=auth_headers(token))
        assert r.status_code == 403

    def test_staff_cannot_create_staff(self, client, db):
        u = create_user(db, "staff3@test.com", "Valid@12345", models.UserRole.internal)
        token = login(client, "staff3@test.com", "Valid@12345")
        r = client.post("/api/users/staff", json={
            "name": "New Staff", "email": "newstaff@test.com", "password": "Valid@12345"
        }, headers=auth_headers(token))
        assert r.status_code == 403

    def test_admin_can_create_staff(self, client, db):
        u = create_user(db, "admin@test.com", "Valid@12345", models.UserRole.admin)
        token = login(client, "admin@test.com", "Valid@12345")
        r = client.post("/api/users/staff", json={
            "name": "New Staff", "email": "newstaff2@test.com", "password": "Valid@12345", "role": "internal"
        }, headers=auth_headers(token))
        assert r.status_code == 201


# ---------------------------------------------------------------------------
# 4. Status transitions
# ---------------------------------------------------------------------------

class TestStatusTransitions:
    def test_valid_transition_draft_to_quotation(self, client, db):
        admin = create_user(db, "adm@test.com", "Valid@12345", models.UserRole.admin)
        cust = models.Customer(name="C", email="c@c.com")
        db.add(cust)
        db.flush()
        plan = create_plan(db)
        sub = create_subscription(db, cust, plan)
        token = login(client, "adm@test.com", "Valid@12345")
        r = client.post(f"/api/subscriptions/{sub.id}/transition",
                        json={"action": "quotation"}, headers=auth_headers(token))
        assert r.status_code == 200
        assert r.json()["status"] == "quotation"

    def test_invalid_transition_draft_to_active(self, client, db):
        admin = create_user(db, "adm2@test.com", "Valid@12345", models.UserRole.admin)
        cust = models.Customer(name="C", email="c2@c.com")
        db.add(cust)
        db.flush()
        plan = create_plan(db)
        sub = create_subscription(db, cust, plan)
        token = login(client, "adm2@test.com", "Valid@12345")
        r = client.post(f"/api/subscriptions/{sub.id}/transition",
                        json={"action": "active"}, headers=auth_headers(token))
        assert r.status_code == 400

    def test_plan_no_pause_prevents_pause(self, client, db):
        admin = create_user(db, "adm3@test.com", "Valid@12345", models.UserRole.admin)
        cust = models.Customer(name="C", email="c3@c.com")
        db.add(cust)
        db.flush()
        plan = create_plan(db, allow_pause=False)
        sub = create_subscription(db, cust, plan, models.SubscriptionStatus.active)
        token = login(client, "adm3@test.com", "Valid@12345")
        r = client.post(f"/api/subscriptions/{sub.id}/transition",
                        json={"action": "pause"}, headers=auth_headers(token))
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# 5. Idempotent billing
# ---------------------------------------------------------------------------

class TestIdempotentBilling:
    def test_billing_run_twice_no_duplicates(self, db):
        from app.billing import run_billing
        # Create the minimal data
        tax = create_tax(db)
        product = create_product(db)
        plan = create_plan(db)
        cust = models.Customer(name="BillingTest", email="bt@test.com")
        db.add(cust)
        db.flush()
        sub = create_subscription(db, cust, plan, models.SubscriptionStatus.active,
                                  lines=[{"product_id": product.id, "unit_price": Decimal("1000.00"), "tax_id": tax.id}])
        sub.next_billing_date = date.today()
        db.commit()

        result1 = run_billing(db, today=date.today())
        result2 = run_billing(db, today=date.today())

        assert result1["created"] == 1
        assert result2["created"] == 0  # idempotent
        assert result2["skipped"] == 1

        inv_count = db.query(models.Invoice).filter(
            models.Invoice.subscription_id == sub.id
        ).count()
        assert inv_count == 1


# ---------------------------------------------------------------------------
# 6. Tax calculation
# ---------------------------------------------------------------------------

class TestTaxCalculation:
    def test_tax_applied_correctly(self, db):
        from app.billing import run_billing
        tax = create_tax(db)
        product = create_product(db)  # sales_price=1000
        plan = create_plan(db)
        cust = models.Customer(name="TaxTest", email="tax@test.com")
        db.add(cust)
        db.flush()
        sub = create_subscription(db, cust, plan, models.SubscriptionStatus.active,
                                  lines=[{"product_id": product.id, "unit_price": Decimal("1000.00"), "tax_id": tax.id}])
        sub.next_billing_date = date.today()
        db.commit()

        run_billing(db, today=date.today())
        inv = db.query(models.Invoice).filter(models.Invoice.subscription_id == sub.id).first()

        assert inv is not None
        assert float(inv.subtotal) == 1000.0
        assert float(inv.tax_total) == 180.0  # 18%
        assert float(inv.total) == 1180.0


# ---------------------------------------------------------------------------
# 7. Discount: auto-apply, expiry, usage limit
# ---------------------------------------------------------------------------

class TestDiscounts:
    def test_expired_discount_not_applied(self, db):
        from app.billing import run_billing
        tax = create_tax(db)
        product = create_product(db)
        plan = create_plan(db)
        cust = models.Customer(name="DiscTest", email="disc@test.com")
        db.add(cust)
        db.flush()
        sub = create_subscription(db, cust, plan, models.SubscriptionStatus.active,
                                  lines=[{"product_id": product.id, "unit_price": Decimal("1000.00"), "tax_id": tax.id}])
        sub.next_billing_date = date.today()

        # Expired discount
        disc = models.DiscountRule(
            name="Expired", type=models.DiscountType.percentage, value=Decimal("10"),
            end_date=date.today() - timedelta(days=1),
            applies_to=models.DiscountAppliesTo.subscription,
            is_active=True,
        )
        db.add(disc)
        db.commit()

        run_billing(db, today=date.today())
        inv = db.query(models.Invoice).filter(models.Invoice.subscription_id == sub.id).first()
        assert float(inv.discount_total) == 0.0

    def test_usage_limit_discount_not_applied(self, db):
        from app.billing import run_billing
        tax = create_tax(db)
        product = create_product(db)
        plan = create_plan(db)
        cust = models.Customer(name="DiscTest2", email="disc2@test.com")
        db.add(cust)
        db.flush()
        sub = create_subscription(db, cust, plan, models.SubscriptionStatus.active,
                                  lines=[{"product_id": product.id, "unit_price": Decimal("1000.00"), "tax_id": tax.id}])
        sub.next_billing_date = date.today()

        # Usage limit reached
        disc = models.DiscountRule(
            name="Used Up", type=models.DiscountType.percentage, value=Decimal("10"),
            usage_limit=5, times_used=5,
            applies_to=models.DiscountAppliesTo.subscription,
            is_active=True,
        )
        db.add(disc)
        db.commit()

        run_billing(db, today=date.today())
        inv = db.query(models.Invoice).filter(models.Invoice.subscription_id == sub.id).first()
        assert float(inv.discount_total) == 0.0

    def test_active_discount_applied(self, db):
        from app.billing import run_billing
        tax = create_tax(db)
        product = create_product(db)
        plan = create_plan(db)
        cust = models.Customer(name="DiscTest3", email="disc3@test.com")
        db.add(cust)
        db.flush()
        sub = create_subscription(db, cust, plan, models.SubscriptionStatus.active,
                                  lines=[{"product_id": product.id, "unit_price": Decimal("1000.00"), "tax_id": tax.id}])
        sub.next_billing_date = date.today()

        disc = models.DiscountRule(
            name="Active 10%", type=models.DiscountType.percentage, value=Decimal("10"),
            applies_to=models.DiscountAppliesTo.subscription,
            is_active=True,
        )
        db.add(disc)
        db.commit()

        run_billing(db, today=date.today())
        inv = db.query(models.Invoice).filter(models.Invoice.subscription_id == sub.id).first()
        assert float(inv.discount_total) == 100.0  # 10% of 1000


# ---------------------------------------------------------------------------
# 8. Partial payments -> paid
# ---------------------------------------------------------------------------

class TestPayments:
    def test_partial_then_full_payment(self, db):
        from app.billing import record_payment
        tax = create_tax(db)
        product = create_product(db)
        plan = create_plan(db)
        cust = models.Customer(name="PayTest", email="pay@test.com")
        db.add(cust)
        db.flush()

        inv = models.Invoice(
            number="INV-TEST-01",
            subscription_id=None,
            customer_id=cust.id,
            billing_period_start=date.today(),
            billing_period_end=date.today(),
            issue_date=date.today(),
            due_date=date.today(),
            status=models.InvoiceStatus.confirmed,
            subtotal=Decimal("1000.00"),
            discount_total=Decimal("0.00"),
            tax_total=Decimal("180.00"),
            total=Decimal("1180.00"),
            amount_paid=Decimal("0.00"),
            balance_due=Decimal("1180.00"),
        )
        db.add(inv)
        db.commit()

        # Partial payment
        record_payment(db, inv, models.PaymentMethod.cash, Decimal("580.00"), date.today(), None, None)
        db.refresh(inv)
        assert inv.status == models.InvoiceStatus.confirmed
        assert float(inv.balance_due) == 600.00

        # Full payment
        record_payment(db, inv, models.PaymentMethod.cash, Decimal("600.00"), date.today(), None, None)
        db.refresh(inv)
        assert inv.status == models.InvoiceStatus.paid
        assert float(inv.balance_due) == 0.00

    def test_overpayment_rejected(self, db):
        from app.billing import record_payment
        cust = models.Customer(name="OPTest", email="op@test.com")
        db.add(cust)
        db.flush()

        inv = models.Invoice(
            number="INV-TEST-02",
            subscription_id=None,
            customer_id=cust.id,
            billing_period_start=date.today(),
            billing_period_end=date.today(),
            issue_date=date.today(),
            due_date=date.today(),
            status=models.InvoiceStatus.confirmed,
            subtotal=Decimal("100.00"),
            discount_total=Decimal("0.00"),
            tax_total=Decimal("18.00"),
            total=Decimal("118.00"),
            amount_paid=Decimal("0.00"),
            balance_due=Decimal("118.00"),
        )
        db.add(inv)
        db.commit()

        with pytest.raises(ValueError, match="exceeds balance"):
            record_payment(db, inv, models.PaymentMethod.cash, Decimal("200.00"), date.today(), None, None)


# ---------------------------------------------------------------------------
# 9. Overdue detection
# ---------------------------------------------------------------------------

class TestOverdueDetection:
    def test_overdue_invoice_detected(self, client, db):
        admin = create_user(db, "adm_od@test.com", "Valid@12345", models.UserRole.admin)
        token = login(client, "adm_od@test.com", "Valid@12345")

        cust = models.Customer(name="OD", email="od@test.com")
        db.add(cust)
        db.flush()

        inv = models.Invoice(
            number="INV-OD-01",
            subscription_id=None,
            customer_id=cust.id,
            billing_period_start=date.today() - timedelta(days=30),
            billing_period_end=date.today() - timedelta(days=1),
            issue_date=date.today() - timedelta(days=30),
            due_date=date.today() - timedelta(days=10),  # overdue!
            status=models.InvoiceStatus.confirmed,
            subtotal=Decimal("100.00"),
            discount_total=Decimal("0.00"),
            tax_total=Decimal("18.00"),
            total=Decimal("118.00"),
            amount_paid=Decimal("0.00"),
            balance_due=Decimal("118.00"),
        )
        db.add(inv)
        db.commit()

        r = client.get("/api/reports/overdue-invoices", headers=auth_headers(token))
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        assert any(i["id"] == inv.id for i in data["items"])


# ---------------------------------------------------------------------------
# 10. Product variant price
# ---------------------------------------------------------------------------

class TestProductVariant:
    def test_effective_price(self, client, db):
        admin = create_user(db, "adm_pv@test.com", "Valid@12345", models.UserRole.admin)
        token = login(client, "adm_pv@test.com", "Valid@12345")

        r = client.post("/api/products", json={
            "name": "CRM Test",
            "type": "software",
            "sales_price": 2999.0,
            "cost_price": 500.0,
            "variants": [{"attribute": "Brand", "value": "Odoo", "extra_price": 560.0}]
        }, headers=auth_headers(token))

        assert r.status_code == 201
        data = r.json()
        assert len(data["variants"]) == 1
        assert data["variants"][0]["effective_price"] == 3559.0  # 2999 + 560
