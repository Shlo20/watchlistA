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


class ListItemUpdate(BaseModel):
    quantity: int = Field(ge=1)


class ListItemOut(BaseModel):
    id: int
    product_id: int | None
    product_name: str | None = None
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
    has_been_sent: bool = False


def build_list_out(lst, has_been_sent: bool = False) -> ListOut:
    """Construct a ListOut from an ORM List with eagerly-loaded items/products."""
    items_out = []
    for item in lst.items:
        product_name: str | None = None
        if item.product_id is not None:
            try:
                product_name = item.product.name if item.product else None
            except Exception:
                product_name = None
        items_out.append(ListItemOut(
            id=item.id,
            product_id=item.product_id,
            product_name=product_name,
            custom_product_name=item.custom_product_name,
            quantity=item.quantity,
            position=item.position,
        ))
    return ListOut(
        id=lst.id,
        title=lst.title,
        items=items_out,
        created_at=lst.created_at,
        has_been_sent=has_been_sent,
    )
