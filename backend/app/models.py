"""SQLAlchemy ORM models for the Brightloop Subscription Management System."""
from __future__ import annotations

import enum
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, ForeignKey, Index,
    Integer, Numeric, String, Text, UniqueConstraint, func,
)
from sqlalchemy.orm import relationship

from app.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    admin = "admin"
    internal = "internal"
    customer = "customer"


class ProductType(str, enum.Enum):
    service = "service"
    goods = "goods"
    software = "software"
    addon = "addon"


class BillingPeriod(str, enum.Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    yearly = "yearly"


class SubscriptionStatus(str, enum.Enum):
    draft = "draft"
    quotation = "quotation"
    confirmed = "confirmed"
    active = "active"
    closed = "closed"


class InvoiceStatus(str, enum.Enum):
    draft = "draft"
    confirmed = "confirmed"
    paid = "paid"
    cancelled = "cancelled"


class PaymentMethod(str, enum.Enum):
    card = "card"
    bank_transfer = "bank_transfer"
    cash = "cash"
    upi = "upi"
    cheque = "cheque"
    other = "other"


class DiscountType(str, enum.Enum):
    fixed = "fixed"
    percentage = "percentage"


class DiscountAppliesTo(str, enum.Enum):
    product = "product"
    subscription = "subscription"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    email = Column(String(320), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.customer)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    reset_tokens = relationship("PasswordResetToken", back_populates="user", cascade="all, delete-orphan")
    customer_profile = relationship("Customer", back_populates="user", uselist=False)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String(256), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="reset_tokens")


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(200), nullable=False)
    email = Column(String(320), nullable=False, index=True)
    phone = Column(String(50), nullable=True)
    company = Column(String(200), nullable=True)
    address = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="customer_profile")
    subscriptions = relationship("Subscription", back_populates="customer")
    invoices = relationship("Invoice", back_populates="customer")


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(300), nullable=False)
    type = Column(Enum(ProductType), nullable=False, default=ProductType.software)
    sales_price = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    cost_price = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    taxes = relationship("ProductTax", back_populates="product", cascade="all, delete-orphan")
    subscription_lines = relationship("SubscriptionLine", back_populates="product")
    invoice_lines = relationship("InvoiceLine", back_populates="product")


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    attribute = Column(String(100), nullable=False)  # e.g. "Brand"
    value = Column(String(100), nullable=False)       # e.g. "Odoo"
    extra_price = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))

    product = relationship("Product", back_populates="variants")
    subscription_lines = relationship("SubscriptionLine", back_populates="variant")
    invoice_lines = relationship("InvoiceLine", back_populates="variant")


class Tax(Base):
    __tablename__ = "taxes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    rate_percent = Column(Numeric(5, 2), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)

    product_taxes = relationship("ProductTax", back_populates="tax", cascade="all, delete-orphan")
    subscription_lines = relationship("SubscriptionLine", back_populates="tax")
    invoice_lines = relationship("InvoiceLine", back_populates="tax")


class ProductTax(Base):
    """Links a tax to a product (M2M via association table)."""
    __tablename__ = "product_taxes"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    tax_id = Column(Integer, ForeignKey("taxes.id", ondelete="CASCADE"), nullable=False)

    product = relationship("Product", back_populates="taxes")
    tax = relationship("Tax", back_populates="product_taxes")


class Plan(Base):
    __tablename__ = "plans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(300), nullable=False)
    price = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    billing_period = Column(Enum(BillingPeriod), nullable=False, default=BillingPeriod.monthly)
    min_quantity = Column(Integer, nullable=False, default=1)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    auto_close_on_end = Column(Boolean, default=False, nullable=False)
    allow_early_close = Column(Boolean, default=True, nullable=False)
    allow_pause = Column(Boolean, default=True, nullable=False)
    allow_renew = Column(Boolean, default=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    subscriptions = relationship("Subscription", back_populates="plan")
    templates = relationship("QuotationTemplate", back_populates="plan")


class QuotationTemplate(Base):
    __tablename__ = "quotation_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(300), nullable=False)
    validity_days = Column(Integer, nullable=False, default=30)
    plan_id = Column(Integer, ForeignKey("plans.id", ondelete="SET NULL"), nullable=True)

    plan = relationship("Plan", back_populates="templates")
    lines = relationship("QuotationTemplateLine", back_populates="template", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="created_from_template")


class QuotationTemplateLine(Base):
    __tablename__ = "quotation_template_lines"

    id = Column(Integer, primary_key=True, index=True)
    template_id = Column(Integer, ForeignKey("quotation_templates.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    variant_id = Column(Integer, ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True)
    quantity = Column(Integer, nullable=False, default=1)

    template = relationship("QuotationTemplate", back_populates="lines")
    product = relationship("Product")
    variant = relationship("ProductVariant")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(String(20), unique=True, nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_id = Column(Integer, ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False)
    start_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=True)
    payment_terms = Column(String(50), nullable=False, default="Immediate")
    status = Column(Enum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.draft, index=True)
    next_billing_date = Column(Date, nullable=True, index=True)
    paused = Column(Boolean, default=False, nullable=False)
    created_from_template_id = Column(Integer, ForeignKey("quotation_templates.id", ondelete="SET NULL"), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    notes = Column(Text, nullable=True)

    customer = relationship("Customer", back_populates="subscriptions")
    plan = relationship("Plan", back_populates="subscriptions")
    lines = relationship("SubscriptionLine", back_populates="subscription", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="subscription")
    created_from_template = relationship("QuotationTemplate", back_populates="subscriptions")
    creator = relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        Index("ix_sub_status_billing", "status", "next_billing_date"),
    )


class SubscriptionLine(Base):
    __tablename__ = "subscription_lines"

    id = Column(Integer, primary_key=True, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="CASCADE"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=False)
    variant_id = Column(Integer, ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    tax_id = Column(Integer, ForeignKey("taxes.id", ondelete="SET NULL"), nullable=True)
    amount = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))

    subscription = relationship("Subscription", back_populates="lines")
    product = relationship("Product", back_populates="subscription_lines")
    variant = relationship("ProductVariant", back_populates="subscription_lines")
    tax = relationship("Tax", back_populates="subscription_lines")


class DiscountRule(Base):
    __tablename__ = "discount_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(300), nullable=False)
    type = Column(Enum(DiscountType), nullable=False, default=DiscountType.percentage)
    value = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    min_purchase = Column(Numeric(12, 2), nullable=True)
    min_quantity = Column(Integer, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    usage_limit = Column(Integer, nullable=True)
    times_used = Column(Integer, nullable=False, default=0)
    applies_to = Column(Enum(DiscountAppliesTo), nullable=False, default=DiscountAppliesTo.subscription)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True)
    plan_id = Column(Integer, ForeignKey("plans.id", ondelete="SET NULL"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    product = relationship("Product")
    subscription = relationship("Subscription")
    plan = relationship("Plan")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    number = Column(String(20), unique=True, nullable=False, index=True)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="RESTRICT"), nullable=False, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True)
    billing_period_start = Column(Date, nullable=False)
    billing_period_end = Column(Date, nullable=False)
    issue_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    status = Column(Enum(InvoiceStatus), nullable=False, default=InvoiceStatus.draft, index=True)
    subtotal = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    discount_total = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    tax_total = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    total = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    amount_paid = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    balance_due = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    sent_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    subscription = relationship("Subscription", back_populates="invoices")
    customer = relationship("Customer", back_populates="invoices")
    lines = relationship("InvoiceLine", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="invoice")

    __table_args__ = (
        UniqueConstraint("subscription_id", "billing_period_start", name="uq_invoice_sub_period"),
        Index("ix_invoice_status_due", "status", "due_date"),
    )


class InvoiceLine(Base):
    __tablename__ = "invoice_lines"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    description = Column(String(500), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="SET NULL"), nullable=True)
    variant_id = Column(Integer, ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    tax_id = Column(Integer, ForeignKey("taxes.id", ondelete="SET NULL"), nullable=True)
    tax_rate = Column(Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    discount = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    amount = Column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))

    invoice = relationship("Invoice", back_populates="lines")
    product = relationship("Product", back_populates="invoice_lines")
    variant = relationship("ProductVariant", back_populates="invoice_lines")
    tax = relationship("Tax", back_populates="invoice_lines")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=False, index=True)
    method = Column(Enum(PaymentMethod), nullable=False, default=PaymentMethod.bank_transfer)
    amount = Column(Numeric(12, 2), nullable=False)
    date = Column(Date, nullable=False)
    note = Column(Text, nullable=True)
    recorded_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    invoice = relationship("Invoice", back_populates="payments")
    recorder = relationship("User", foreign_keys=[recorded_by])


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)
    entity = Column(String(100), nullable=False)
    entity_id = Column(Integer, nullable=True)
    detail = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
