"""Inbox and item check-off endpoints."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.list import List, ListItem
from app.models.send import Send, SendItemState
from app.models.user import User
from app.schemas.send import (
    InboxSendOut,
    SendItemStateOut,
    SendItemStateUpdate,
    build_inbox_send_out,
)


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

    db.commit()
    db.refresh(state)
    return SendItemStateOut(
        list_item_id=state.list_item_id,
        checked=state.checked,
        received_quantity=state.received_quantity,
    )
