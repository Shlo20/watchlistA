"""Pydantic schemas for Send, SendItemState, and related types."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RecipientIn(BaseModel):
    contact_id: int | None = None
    phone: str | None = None  # raw input, normalised in the handler

    @model_validator(mode="after")
    def require_exactly_one(self) -> "RecipientIn":
        has_contact = self.contact_id is not None
        has_phone = self.phone is not None
        if not has_contact and not has_phone:
            raise ValueError("Each recipient needs contact_id or phone")
        if has_contact and has_phone:
            raise ValueError("Provide contact_id or phone, not both")
        return self


class SendCreate(BaseModel):
    recipients: list[RecipientIn] = Field(min_length=1)


class SendItemStateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    list_item_id: int
    checked: bool
    received_quantity: int | None


class SendItemStateUpdate(BaseModel):
    checked: bool | None = None
    received_quantity: int | None = None


class SendOut(BaseModel):
    id: int
    list_id: int
    recipient_phone: str
    recipient_user_id: int | None
    contact_id: int | None
    created_at: datetime
    wa_link: str | None
    item_states: list[SendItemStateOut]


def build_send_out(send, wa_link: str | None = None) -> SendOut:
    """Construct a SendOut from an ORM Send object."""
    return SendOut(
        id=send.id,
        list_id=send.list_id,
        recipient_phone=send.recipient_phone,
        recipient_user_id=send.recipient_user_id,
        contact_id=send.contact_id,
        created_at=send.created_at,
        wa_link=wa_link,
        item_states=[
            SendItemStateOut(
                list_item_id=s.list_item_id,
                checked=s.checked,
                received_quantity=s.received_quantity,
            )
            for s in send.item_states
        ],
    )
