"""Pydantic schemas for Send, SendItemState, and related types."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RecipientIn(BaseModel):
    contact_id: int | None = None
    phone: str | None = None  # raw input, normalised in the handler
    # None = smart default: registered→inbox, unregistered→whatsapp
    to_inbox: bool | None = None
    to_whatsapp: bool | None = None

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
    unit_price_cents: int | None = None


class SendItemStateUpdate(BaseModel):
    checked: bool | None = None
    received_quantity: int | None = None
    unit_price_cents: int | None = None


class SendOut(BaseModel):
    id: int
    list_id: int
    recipient_phone: str
    recipient_user_id: int | None
    contact_id: int | None
    created_at: datetime
    wa_link: str | None
    deliver_to_inbox: bool
    item_states: list[SendItemStateOut]


class InboxItemOut(BaseModel):
    id: int
    product_id: int | None
    product_name: str | None
    custom_product_name: str | None
    quantity: int


class InboxSendOut(BaseModel):
    id: int
    list_id: int
    list_title: str | None
    sender_name: str | None
    sender_business_name: str | None = None
    items: list[InboxItemOut]
    item_states: list[SendItemStateOut]
    created_at: datetime
    quoted_at: datetime | None = None


class QuoteItemOut(BaseModel):
    list_item_id: int
    name: str
    quantity: int
    unit_price_cents: int | None


class QuoteOut(BaseModel):
    send_id: int
    supplier_name: str | None
    quoted_at: datetime
    items: list[QuoteItemOut]
    total_cents: int


class QuoteWaLinkOut(BaseModel):
    wa_link: str


def build_inbox_send_out(send) -> InboxSendOut:
    """Build the richer inbox payload that includes list title and items."""
    lst = send.parent_list
    return InboxSendOut(
        id=send.id,
        list_id=send.list_id,
        list_title=lst.title if lst else None,
        sender_name=send.sender.name if send.sender else None,
        sender_business_name=send.sender.business_name if send.sender else None,
        items=[
            InboxItemOut(
                id=item.id,
                product_id=item.product_id,
                product_name=item.product.name if item.product else None,
                custom_product_name=item.custom_product_name,
                quantity=item.quantity,
            )
            for item in (lst.items if lst else [])
        ],
        item_states=[
            SendItemStateOut(
                list_item_id=s.list_item_id,
                checked=s.checked,
                received_quantity=s.received_quantity,
                unit_price_cents=s.unit_price_cents,
            )
            for s in send.item_states
        ],
        created_at=send.created_at,
        quoted_at=send.quoted_at,
    )


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
        deliver_to_inbox=send.deliver_to_inbox,
        item_states=[
            SendItemStateOut(
                list_item_id=s.list_item_id,
                checked=s.checked,
                received_quantity=s.received_quantity,
                unit_price_cents=s.unit_price_cents,
            )
            for s in send.item_states
        ],
    )
