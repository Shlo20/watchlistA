"""Inbox and item check-off endpoints."""
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
    SendOut,
    build_inbox_send_out,
    build_send_out,
)


router = APIRouter(tags=["sends"])


@router.get("/inbox", response_model=list[InboxSendOut])
def inbox(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """All sends where the current user is the recipient, newest first."""
    sends = (
        db.query(Send)
        .filter(Send.recipient_user_id == user.id)
        .options(
            joinedload(Send.parent_list).joinedload(List.items).joinedload(ListItem.product),
            joinedload(Send.sender),
            joinedload(Send.item_states),
        )
        .order_by(Send.created_at.desc())
        .all()
    )
    return [build_inbox_send_out(s) for s in sends]


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
