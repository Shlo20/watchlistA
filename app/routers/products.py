"""Product catalog routes."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.low_stock_flag import LowStockFlag
from app.models.product import Product, ProductCategory
from app.models.user import User
from app.schemas.product import ProductCreate, ProductOut


router = APIRouter(prefix="/products", tags=["products"])


def _flagged_ids(user: User, db: Session) -> set[int]:
    """Return the set of product_ids the user has flagged low."""
    rows = db.query(LowStockFlag.product_id).filter(LowStockFlag.user_id == user.id).all()
    return {r[0] for r in rows}


def _to_out(product: Product, low_ids: set[int]) -> ProductOut:
    out = ProductOut.model_validate(product)
    out.is_low = product.id in low_ids
    return out


# ── /products/low must come BEFORE /products/{product_id} ──────────────────

@router.get("/low", response_model=list[ProductOut])
def list_low_products(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return all products the current user has flagged as running low."""
    flags = (
        db.query(LowStockFlag)
        .filter(LowStockFlag.user_id == user.id)
        .all()
    )
    product_ids = [f.product_id for f in flags]
    if not product_ids:
        return []
    products = db.query(Product).filter(Product.id.in_(product_ids)).order_by(Product.name).all()
    return [_to_out(p, set(product_ids)) for p in products]


@router.post("/{product_id}/low", response_model=ProductOut, status_code=status.HTTP_200_OK)
def flag_low(
    product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Flag a product as running low for the current user (idempotent)."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

    existing = db.query(LowStockFlag).filter(
        LowStockFlag.user_id == user.id,
        LowStockFlag.product_id == product_id,
    ).first()
    if not existing:
        db.add(LowStockFlag(user_id=user.id, product_id=product_id))
        db.commit()

    out = ProductOut.model_validate(product)
    out.is_low = True
    return out


@router.delete("/{product_id}/low", status_code=status.HTTP_204_NO_CONTENT)
def unflag_low(
    product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Remove the running-low flag for the current user."""
    db.query(LowStockFlag).filter(
        LowStockFlag.user_id == user.id,
        LowStockFlag.product_id == product_id,
    ).delete()
    db.commit()


# ── standard catalog routes ─────────────────────────────────────────────────

@router.get("", response_model=list[ProductOut])
def list_products(
    category: ProductCategory | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Anyone authenticated can browse the catalog."""
    q = db.query(Product).filter(Product.is_active.is_(True))
    if category:
        q = q.filter(Product.category == category)
    if search:
        normalized = search.strip().lower().replace(" ", "")
        if normalized:
            q = q.filter(
                func.replace(func.lower(Product.name), " ", "").like(f"%{normalized}%")
            )
    products = q.order_by(Product.name).all()
    low_ids = _flagged_ids(user, db)
    return [_to_out(p, low_ids) for p in products]


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Any authenticated user can add new SKUs to the catalog."""
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/{product_id}", response_model=ProductOut)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    low_ids = _flagged_ids(user, db)
    return _to_out(product, low_ids)
