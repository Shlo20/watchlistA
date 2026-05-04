"""Product catalog routes."""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.product import Product, ProductCategory
from app.models.user import UserRole
from app.schemas.product import ProductCreate, ProductOut


router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductOut])
def list_products(
    category: ProductCategory | None = Query(default=None),
    search: str | None = Query(default=None, min_length=1, max_length=100),
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    """Anyone authenticated can browse the catalog."""
    q = db.query(Product).filter(Product.is_active.is_(True))
    if category:
        q = q.filter(Product.category == category)
    if search:
        normalized = search.strip().lower().replace(" ", "")
        if normalized:
            q = q.filter(
                func.replace(func.lower(Product.name)," ","").like(f"%{normalized}%")
            )
    return q.order_by(Product.name).all()


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreate,
    db: Session = Depends(get_db),
    _buyer=Depends(require_role(UserRole.BUYER)),
):
    """Only buyers can add new SKUs to the catalog."""
    product = Product(**payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/{product_id}", response_model=ProductOut)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
    _user=Depends(get_current_user),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return product
