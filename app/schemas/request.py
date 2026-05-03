"""Pydantic schemas for restock requests."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.request import RequestStatus


class RequestCreate(BaseModel):
    """Either product_id OR custom_product_name must be set, not both."""
    product_id: int | None = None
    custom_product_name: str | None = Field(default=None, min_length=1, max_length=200)
    quantity: int = Field(gt=0, le=10000)
    notes: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def exactly_one_product_source(self):
        has_id = self.product_id is not None
        has_name = self.custom_product_name is not None and self.custom_product_name.strip() != ""
        if has_id == has_name:  # both true OR both false
            raise ValueError(
                "Provide either product_id (from catalog) or custom_product_name, not both."
            )
        return self


class RequestStatusUpdate(BaseModel):
    status: RequestStatus


class ClearAllResponse(BaseModel):
    cleared_count: int
    request_ids: list[int]


class RequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    requester_id: int
    product_id: int | None
    custom_product_name: str | None
    quantity: int
    notes: str | None
    status: RequestStatus
    created_at: datetime
    updated_at: datetime
