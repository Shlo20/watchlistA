"""Pydantic schemas for List and ListItem."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ListItemIn(BaseModel):
    product_id: int | None = None
    custom_product_name: str | None = Field(default=None, max_length=200)
    quantity: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def require_exactly_one_source(self) -> "ListItemIn":
        has_product = self.product_id is not None
        has_name = bool(self.custom_product_name)
        if not has_product and not has_name:
            raise ValueError("Each item needs product_id or custom_product_name")
        if has_product and has_name:
            raise ValueError("Provide product_id or custom_product_name, not both")
        return self


class ListItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int | None
    custom_product_name: str | None
    quantity: int
    position: int


class ListCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    items: list[ListItemIn] = Field(default_factory=list)


class ListUpdate(BaseModel):
    title: str | None = None         # None with key present → clear title
    items: list[ListItemIn] | None = None  # None → keep existing; [] → clear all


class ListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str | None
    items: list[ListItemOut]
    created_at: datetime
