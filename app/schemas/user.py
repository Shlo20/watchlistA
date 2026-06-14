"""Pydantic schemas for users and auth."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RequestCodePayload(BaseModel):
    phone: str = Field(min_length=7, max_length=20)


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=7, max_length=20)
    carrier: str | None = Field(default=None, max_length=20)
    password: str = Field(min_length=8, max_length=100)
    code: str = Field(min_length=1, max_length=10)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    phone: str
    plan: str
    created_at: datetime


class LoginRequest(BaseModel):
    phone: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
