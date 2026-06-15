"""Contact address-book routes — owner-scoped to the authenticated user."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.phone import normalize_phone
from app.models.contact import Contact
from app.models.user import User
from app.schemas.contact import ContactCreate, ContactOut, ContactUpdate


router = APIRouter(prefix="/contacts", tags=["contacts"])


def _normalize_or_422(raw: str) -> str:
    try:
        return normalize_phone(raw)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))


def _get_owned_or_404(contact_id: int, user: User, db: Session) -> Contact:
    contact = (
        db.query(Contact)
        .filter(Contact.id == contact_id, Contact.owner_user_id == user.id)
        .first()
    )
    if not contact:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")
    return contact


@router.post("", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
def create_contact(
    payload: ContactCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    phone = _normalize_or_422(payload.phone)
    if db.query(Contact).filter(
        Contact.owner_user_id == user.id, Contact.phone == phone
    ).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Contact with this phone already exists")
    linked_user = db.query(User).filter(User.phone == phone).first()
    contact = Contact(
        owner_user_id=user.id,
        nickname=payload.nickname,
        phone=phone,
        linked_user_id=linked_user.id if linked_user else None,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.get("", response_model=list[ContactOut])
def list_contacts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return (
        db.query(Contact)
        .filter(Contact.owner_user_id == user.id)
        .order_by(Contact.nickname)
        .all()
    )


@router.get("/{contact_id}", response_model=ContactOut)
def get_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return _get_owned_or_404(contact_id, user, db)


@router.patch("/{contact_id}", response_model=ContactOut)
def update_contact(
    contact_id: int,
    payload: ContactUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    contact = _get_owned_or_404(contact_id, user, db)
    if payload.nickname is not None:
        contact.nickname = payload.nickname
    if payload.phone is not None:
        phone = _normalize_or_422(payload.phone)
        # Reject if another of the caller's contacts already uses this phone
        conflict = (
            db.query(Contact)
            .filter(
                Contact.owner_user_id == user.id,
                Contact.phone == phone,
                Contact.id != contact_id,
            )
            .first()
        )
        if conflict:
            raise HTTPException(status.HTTP_409_CONFLICT, "Contact with this phone already exists")
        contact.phone = phone
        # Re-resolve link whenever phone changes
        linked_user = db.query(User).filter(User.phone == phone).first()
        contact.linked_user_id = linked_user.id if linked_user else None
    db.commit()
    db.refresh(contact)
    return contact


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    contact = _get_owned_or_404(contact_id, user, db)
    db.delete(contact)
    db.commit()
