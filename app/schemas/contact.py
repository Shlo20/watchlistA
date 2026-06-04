"""Pydantic schemas for contacts."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ContactCreate(BaseModel):
    nickname: str = Field(min_length=1, max_length=100)
    phone: str  # raw; normalized to E.164 in the handler


class ContactUpdate(BaseModel):
    nickname: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = None  # raw; normalized to E.164 in the handler


class ContactOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_user_id: int
    nickname: str
    phone: str
    linked_user_id: int | None
    created_at: datetime
