"""Pydantic schemas for products."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.product import ProductCategory


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    category: ProductCategory
    brand: str | None = Field(default=None, max_length=100)
    model: str | None = Field(default=None, max_length=100)


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: ProductCategory
    brand: str | None
    model: str | None
    is_active: bool
    created_at: datetime
