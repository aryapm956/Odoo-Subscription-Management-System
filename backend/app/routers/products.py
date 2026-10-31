"""Products, variants, taxes router."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, selectinload

from app import models
from app.auth import get_current_user, require_admin, require_staff_or_admin
from app.database import get_db

router = APIRouter(tags=["products"])


# ---------------------------------------------------------------------------
# Product schemas
# ---------------------------------------------------------------------------

class VariantCreate(BaseModel):
    attribute: str
    value: str
    extra_price: Decimal = Decimal("0.00")


class ProductCreate(BaseModel):
    name: str
    type: str = "software"
    sales_price: Decimal = Decimal("0.00")
    cost_price: Decimal = Decimal("0.00")
    notes: Optional[str] = None
    tax_ids: List[int] = []
    variants: List[VariantCreate] = []


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None
    sales_price: Optional[Decimal] = None
    cost_price: Optional[Decimal] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None
    tax_ids: Optional[List[int]] = None


def product_to_dict(p: models.Product) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "type": p.type.value,
        "sales_price": float(p.sales_price),
        "cost_price": float(p.cost_price),
        "notes": p.notes,
        "is_active": p.is_active,
        "variants": [
            {
                "id": v.id,
                "attribute": v.attribute,
                "value": v.value,
                "extra_price": float(v.extra_price),
                "effective_price": float(p.sales_price) + float(v.extra_price),
            }
            for v in p.variants
        ],
        "tax_ids": [pt.tax_id for pt in p.taxes],
    }


# ---------------------------------------------------------------------------
# Product endpoints
# ---------------------------------------------------------------------------

products_router = APIRouter(prefix="/products")


@products_router.get("")
def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    q = db.query(models.Product).options(
        selectinload(models.Product.variants),
        selectinload(models.Product.taxes),
    )
    if search:
        q = q.filter(models.Product.name.ilike(f"%{search}%"))
    if is_active is not None:
        q = q.filter(models.Product.is_active == is_active)
    total = q.count()
    products = q.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [product_to_dict(p) for p in products],
    }


@products_router.post("", status_code=201)
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    product = models.Product(
        name=data.name,
        type=models.ProductType(data.type),
        sales_price=data.sales_price,
        cost_price=data.cost_price,
        notes=data.notes,
    )
    db.add(product)
    db.flush()

    for v in data.variants:
        db.add(models.ProductVariant(
            product_id=product.id,
            attribute=v.attribute,
            value=v.value,
            extra_price=v.extra_price,
        ))

    for tax_id in data.tax_ids:
        db.add(models.ProductTax(product_id=product.id, tax_id=tax_id))

    db.commit()
    db.refresh(product)
    # reload relationships
    product = db.query(models.Product).options(
        selectinload(models.Product.variants),
        selectinload(models.Product.taxes),
    ).filter(models.Product.id == product.id).first()
    return product_to_dict(product)


@products_router.get("/{product_id}")
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    product = db.query(models.Product).options(
        selectinload(models.Product.variants),
        selectinload(models.Product.taxes),
    ).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product_to_dict(product)


@products_router.put("/{product_id}")
def update_product(
    product_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    product = db.query(models.Product).options(
        selectinload(models.Product.variants),
        selectinload(models.Product.taxes),
    ).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    for k, v in data.model_dump(exclude_none=True, exclude={"tax_ids"}).items():
        if k == "type":
            setattr(product, k, models.ProductType(v))
        else:
            setattr(product, k, v)

    if data.tax_ids is not None:
        db.query(models.ProductTax).filter(
            models.ProductTax.product_id == product_id
        ).delete()
        for tax_id in data.tax_ids:
            db.add(models.ProductTax(product_id=product_id, tax_id=tax_id))

    db.commit()
    product = db.query(models.Product).options(
        selectinload(models.Product.variants),
        selectinload(models.Product.taxes),
    ).filter(models.Product.id == product_id).first()
    return product_to_dict(product)


@products_router.post("/{product_id}/variants", status_code=201)
def add_variant(
    product_id: int,
    data: VariantCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    variant = models.ProductVariant(
        product_id=product_id,
        attribute=data.attribute,
        value=data.value,
        extra_price=data.extra_price,
    )
    db.add(variant)
    db.commit()
    db.refresh(variant)
    return {
        "id": variant.id,
        "attribute": variant.attribute,
        "value": variant.value,
        "extra_price": float(variant.extra_price),
        "effective_price": float(product.sales_price) + float(variant.extra_price),
    }


@products_router.delete("/{product_id}/variants/{variant_id}", status_code=204)
def delete_variant(
    product_id: int,
    variant_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    v = db.query(models.ProductVariant).filter(
        models.ProductVariant.id == variant_id,
        models.ProductVariant.product_id == product_id,
    ).first()
    if not v:
        raise HTTPException(status_code=404, detail="Variant not found")
    db.delete(v)
    db.commit()


# ---------------------------------------------------------------------------
# Tax endpoints
# ---------------------------------------------------------------------------

taxes_router = APIRouter(prefix="/taxes")


class TaxCreate(BaseModel):
    name: str
    rate_percent: Decimal
    is_default: bool = False


class TaxUpdate(BaseModel):
    name: Optional[str] = None
    rate_percent: Optional[Decimal] = None
    is_active: Optional[bool] = None
    is_default: Optional[bool] = None


def tax_to_dict(t: models.Tax) -> dict:
    return {
        "id": t.id,
        "name": t.name,
        "rate_percent": float(t.rate_percent),
        "is_active": t.is_active,
        "is_default": t.is_default,
    }


@taxes_router.get("")
def list_taxes(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    taxes = db.query(models.Tax).all()
    return [tax_to_dict(t) for t in taxes]


@taxes_router.post("", status_code=201)
def create_tax(
    data: TaxCreate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    if data.is_default:
        db.query(models.Tax).update({"is_default": False})
    tax = models.Tax(
        name=data.name,
        rate_percent=data.rate_percent,
        is_default=data.is_default,
    )
    db.add(tax)
    db.commit()
    db.refresh(tax)
    return tax_to_dict(tax)


@taxes_router.put("/{tax_id}")
def update_tax(
    tax_id: int,
    data: TaxUpdate,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    tax = db.query(models.Tax).filter(models.Tax.id == tax_id).first()
    if not tax:
        raise HTTPException(status_code=404, detail="Tax not found")
    if data.is_default:
        db.query(models.Tax).update({"is_default": False})
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(tax, k, v)
    db.commit()
    db.refresh(tax)
    return tax_to_dict(tax)


@taxes_router.delete("/{tax_id}", status_code=204)
def delete_tax(
    tax_id: int,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_admin),
):
    tax = db.query(models.Tax).filter(models.Tax.id == tax_id).first()
    if not tax:
        raise HTTPException(status_code=404, detail="Tax not found")
    db.delete(tax)
    db.commit()


# Combined router
router = APIRouter()
router.include_router(products_router)
router.include_router(taxes_router)
