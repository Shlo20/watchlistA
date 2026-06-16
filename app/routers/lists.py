"""List CRUD and send-to-recipients endpoint."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.phone import normalize_phone
from app.models.contact import Contact
from app.models.list import List, ListItem
from app.models.send import Send, SendItemState
from app.models.user import User
from app.schemas.list import ListCreate, ListOut, ListUpdate
from app.schemas.send import QuoteItemOut, QuoteOut, SendCreate, SendOut, build_send_out
from app.services.whatsapp import build_wa_link, format_list_body


router = APIRouter(prefix="/lists", tags=["lists"])


def _get_owned_list(list_id: int, user: User, db: Session) -> List:
    lst = db.query(List).filter(List.id == list_id, List.owner_user_id == user.id).first()
    if not lst:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "List not found")
    return lst


def _replace_items(lst: List, items_in, db: Session) -> None:
    for item in list(lst.items):
        db.delete(item)
    db.flush()
    for pos, item_in in enumerate(items_in):
        db.add(ListItem(
            list_id=lst.id,
            product_id=item_in.product_id,
            custom_product_name=item_in.custom_product_name,
            quantity=item_in.quantity,
            position=pos,
        ))


@router.post("", response_model=ListOut, status_code=status.HTTP_201_CREATED)
def create_list(
    payload: ListCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    title = payload.title.strip() if payload.title else None
    if not title:
        now = datetime.now(timezone.utc)
        title = f"Restock — {now.strftime('%b')} {now.day}"
    lst = List(owner_user_id=user.id, title=title)
    db.add(lst)
    db.flush()
    for pos, item_in in enumerate(payload.items):
        db.add(ListItem(
            list_id=lst.id,
            product_id=item_in.product_id,
            custom_product_name=item_in.custom_product_name,
            quantity=item_in.quantity,
            position=pos,
        ))
    db.commit()
    db.refresh(lst)
    return lst


@router.get("", response_model=list[ListOut])
def list_lists(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return (
        db.query(List)
        .filter(List.owner_user_id == user.id)
        .order_by(List.created_at.desc())
        .all()
    )


@router.get("/{list_id}", response_model=ListOut)
def get_list(
    list_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _get_owned_list(list_id, user, db)


@router.patch("/{list_id}", response_model=ListOut)
def update_list(
    list_id: int,
    payload: ListUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    lst = _get_owned_list(list_id, user, db)
    if "title" in payload.model_fields_set:
        lst.title = payload.title
    if payload.items is not None:
        _replace_items(lst, payload.items, db)
    db.commit()
    db.refresh(lst)
    return lst


@router.delete("/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_list(
    list_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    lst = _get_owned_list(list_id, user, db)
    db.delete(lst)
    db.commit()


@router.post("/{list_id}/send", response_model=list[SendOut], status_code=status.HTTP_201_CREATED)
def send_list(
    list_id: int,
    payload: SendCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Send a list to one or more recipients. Returns one SendOut per recipient."""
    lst = _get_owned_list(list_id, user, db)
    results: list[SendOut] = []

    for recipient_in in payload.recipients:
        phone, contact_id = _resolve_recipient(recipient_in, user, db)

        # Determine if the recipient is an in-system user
        recipient_user = db.query(User).filter(User.phone == phone).first()
        recipient_user_id = recipient_user.id if recipient_user else None

        # Resolve effective channels
        if recipient_user_id is None:
            # Unregistered: inbox is impossible — reject explicit request for it
            if recipient_in.to_inbox is True:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    f"Cannot deliver to inbox: {phone} is not a registered user",
                )
            deliver_to_inbox = False
            do_whatsapp = True  # only option for unregistered; always produce wa_link
        else:
            # Registered: inbox on by default, whatsapp off by default
            deliver_to_inbox = recipient_in.to_inbox if recipient_in.to_inbox is not None else True
            do_whatsapp = recipient_in.to_whatsapp if recipient_in.to_whatsapp is not None else False

        send = Send(
            list_id=lst.id,
            sender_user_id=user.id,
            recipient_phone=phone,
            recipient_user_id=recipient_user_id,
            contact_id=contact_id,
            deliver_to_inbox=deliver_to_inbox,
        )
        db.add(send)
        db.flush()  # populate send.id before inserting states

        for item in lst.items:
            db.add(SendItemState(send_id=send.id, list_item_id=item.id))

        db.commit()
        db.refresh(send)

        wa_link = build_wa_link(phone, format_list_body(lst, lst.items, business_name=user.business_name or None)) if do_whatsapp else None
        results.append(build_send_out(send, wa_link=wa_link))

    return results


@router.get("/{list_id}/quotes", response_model=list[QuoteOut])
def get_list_quotes(
    list_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Return all submitted quotes for a list the caller owns."""
    lst = _get_owned_list(list_id, user, db)
    sends = (
        db.query(Send)
        .filter(Send.list_id == list_id, Send.quoted_at.isnot(None))
        .options(
            joinedload(Send.sender),
            joinedload(Send.item_states),
            joinedload(Send.parent_list).joinedload(List.items).joinedload(ListItem.product),
        )
        .order_by(Send.quoted_at.desc())
        .all()
    )

    results: list[QuoteOut] = []
    for send in sends:
        state_map: dict[int, SendItemState] = {s.list_item_id: s for s in send.item_states}
        items_out: list[QuoteItemOut] = []
        total_cents = 0
        for item in lst.items:
            s = state_map.get(item.id)
            name = (item.product.name if item.product else None) or item.custom_product_name or "Item"
            price = s.unit_price_cents if s else None
            items_out.append(QuoteItemOut(
                list_item_id=item.id,
                name=name,
                quantity=item.quantity,
                unit_price_cents=price,
            ))
            if price is not None:
                total_cents += price * item.quantity
        results.append(QuoteOut(
            send_id=send.id,
            supplier_name=send.sender.name if send.sender else None,
            quoted_at=send.quoted_at,
            items=items_out,
            total_cents=total_cents,
        ))
    return results


def _resolve_recipient(recipient_in, user: User, db: Session) -> tuple[str, int | None]:
    """Return (e164_phone, contact_id_or_None)."""
    if recipient_in.contact_id is not None:
        contact = (
            db.query(Contact)
            .filter(Contact.id == recipient_in.contact_id, Contact.owner_user_id == user.id)
            .first()
        )
        if not contact:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Contact {recipient_in.contact_id} not found or not yours",
            )
        return contact.phone, contact.id
    # Raw phone path
    try:
        return normalize_phone(recipient_in.phone), None
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
