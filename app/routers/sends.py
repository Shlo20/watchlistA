"""Inbox, item check-off, and quote endpoints."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.list import List, ListItem
from app.models.low_stock_flag import LowStockFlag
from app.models.send import Send, SendItemState
from app.models.user import User
from app.schemas.send import (
    InboxSendOut,
    QuoteWaLinkOut,
    SendItemStateOut,
    SendItemStateUpdate,
    build_inbox_send_out,
)
from app.services.whatsapp import build_wa_link, format_priced_body


router = APIRouter(tags=["sends"])


def _load_send_full(db: Session, send_id: int) -> Send | None:
    return (
        db.query(Send)
        .filter(Send.id == send_id)
        .options(
            joinedload(Send.parent_list).joinedload(List.items).joinedload(ListItem.product),
            joinedload(Send.sender),
            joinedload(Send.item_states),
        )
        .first()
    )


@router.get("/inbox", response_model=list[InboxSendOut])
def inbox(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """All non-dismissed sends where the current user is the recipient, newest first."""
    sends = (
        db.query(Send)
        .filter(
            Send.recipient_user_id == user.id,
            Send.dismissed_at.is_(None),
            Send.deliver_to_inbox == True,  # noqa: E712
        )
        .options(
            joinedload(Send.parent_list).joinedload(List.items).joinedload(ListItem.product),
            joinedload(Send.sender),
            joinedload(Send.item_states),
        )
        .order_by(Send.created_at.desc())
        .all()
    )
    return [build_inbox_send_out(s) for s in sends]


@router.post("/sends/{send_id}/mark-all-received", response_model=InboxSendOut)
def mark_all_received(
    send_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Set all item states to checked=True and received_quantity=item.quantity."""
    send = _load_send_full(db, send_id)
    if not send:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Send not found")

    lst = send.parent_list
    is_recipient = send.recipient_user_id == user.id
    is_owner = lst is not None and lst.owner_user_id == user.id
    if not is_recipient and not is_owner:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized")

    item_qty = {item.id: item.quantity for item in (lst.items if lst else [])}
    for state in send.item_states:
        state.checked = True
        if state.list_item_id in item_qty:
            state.received_quantity = item_qty[state.list_item_id]

    # Auto-unflag low-stock for all catalog products on this list (for the list owner)
    if lst:
        product_ids = [item.product_id for item in lst.items if item.product_id]
        if product_ids:
            db.query(LowStockFlag).filter(
                LowStockFlag.user_id == lst.owner_user_id,
                LowStockFlag.product_id.in_(product_ids),
            ).delete(synchronize_session=False)

    db.commit()
    send = _load_send_full(db, send_id)
    return build_inbox_send_out(send)


@router.post("/sends/{send_id}/dismiss", status_code=204)
def dismiss_send(
    send_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Soft-dismiss a send for the recipient. Non-destructive — send record is kept."""
    send = db.query(Send).filter(Send.id == send_id).first()
    if not send:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Send not found")
    if send.recipient_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized")
    send.dismissed_at = datetime.now(timezone.utc)
    db.commit()


@router.post("/inbox/clear", status_code=204)
def clear_inbox(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Dismiss all current user's non-dismissed received sends."""
    db.query(Send).filter(
        Send.recipient_user_id == user.id,
        Send.dismissed_at.is_(None),
    ).update({"dismissed_at": datetime.now(timezone.utc)})
    db.commit()


@router.patch(
    "/sends/{send_id}/items/{list_item_id}",
    response_model=SendItemStateOut,
)
def check_off_item(
    send_id: int,
    list_item_id: int,
    payload: SendItemStateUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update checked/received_quantity for one item in a send.

    Allowed for the send's recipient OR the list owner. Third parties get 403.
    """
    send = db.query(Send).filter(Send.id == send_id).first()
    if not send:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Send not found")

    lst = db.query(List).filter(List.id == send.list_id).first()

    is_recipient = send.recipient_user_id == user.id
    is_owner = lst is not None and lst.owner_user_id == user.id
    if not is_recipient and not is_owner:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized")

    state = (
        db.query(SendItemState)
        .filter(
            SendItemState.send_id == send_id,
            SendItemState.list_item_id == list_item_id,
        )
        .first()
    )
    if not state:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Item state not found")

    if payload.checked is not None:
        state.checked = payload.checked
    if "received_quantity" in payload.model_fields_set:
        state.received_quantity = payload.received_quantity
    if "unit_price_cents" in payload.model_fields_set:
        state.unit_price_cents = payload.unit_price_cents

    # Auto-unflag when a catalog item is marked received (for the list owner)
    if payload.checked is True and lst:
        list_item = db.query(ListItem).filter(ListItem.id == list_item_id).first()
        if list_item and list_item.product_id:
            db.query(LowStockFlag).filter(
                LowStockFlag.user_id == lst.owner_user_id,
                LowStockFlag.product_id == list_item.product_id,
            ).delete(synchronize_session=False)

    db.commit()
    db.refresh(state)
    return SendItemStateOut(
        list_item_id=state.list_item_id,
        checked=state.checked,
        received_quantity=state.received_quantity,
        unit_price_cents=state.unit_price_cents,
    )


@router.post("/sends/{send_id}/submit-quote", response_model=InboxSendOut)
def submit_quote(
    send_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Recipient marks their priced quote as submitted. Sets quoted_at = now."""
    send = _load_send_full(db, send_id)
    if not send:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Send not found")
    if send.recipient_user_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the recipient can submit a quote")
    send.quoted_at = datetime.now(timezone.utc)
    db.commit()
    send = _load_send_full(db, send_id)
    return build_inbox_send_out(send)


@router.get("/sends/{send_id}/quote-wa-link", response_model=QuoteWaLinkOut)
def get_quote_wa_link(
    send_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return a priced wa.me link for the quote.

    Supplier (recipient) → link points to the list owner's phone.
    Owner → link points to the supplier's phone.
    Body includes unit prices and a running total.
    """
    send = _load_send_full(db, send_id)
    if not send:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Send not found")

    lst = send.parent_list
    is_recipient = send.recipient_user_id == user.id
    is_owner = lst is not None and lst.owner_user_id == user.id
    if not is_recipient and not is_owner:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized")

    target_phone = send.sender.phone if is_recipient else send.recipient_phone

    price_map = {s.list_item_id: s.unit_price_cents for s in send.item_states}
    body = format_priced_body(lst, lst.items if lst else [], price_map, business_name=user.business_name or None)
    return QuoteWaLinkOut(wa_link=build_wa_link(target_phone, body))
