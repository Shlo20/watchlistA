"""Auth routes: register (two-step with phone verification) and login."""
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.phone import normalize_phone
from app.core.security import create_access_token, hash_password, verify_password
from app.models.contact import Contact
from app.models.send import Send
from app.models.user import User
from app.schemas.user import LoginRequest, RequestCodePayload, TokenResponse, UserCreate, UserOut
from app.services.verification import send_verification_code, verify_code

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/request-code", status_code=status.HTTP_200_OK)
def request_code(payload: RequestCodePayload, db: Session = Depends(get_db)):
    """Step 1 of registration: send a 6-digit OTP to the given phone number.

    Always returns 200 with a generic message — do NOT reveal whether the phone
    is already registered.
    """
    try:
        phone = normalize_phone(payload.phone)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    send_verification_code(phone, db)
    return {"message": "If this number is valid, a verification code has been sent."}


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    """Step 2 of registration: verify OTP, create account, and backfill historical data."""
    try:
        phone = normalize_phone(payload.phone)
    except ValueError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))

    if not verify_code(phone, payload.code, db):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired verification code")

    if db.query(User).filter(User.phone == phone).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Phone already registered")

    user = User(
        name=payload.name,
        phone=phone,
        carrier=payload.carrier,
        password_hash=hash_password(payload.password),
    )
    db.add(user)
    db.flush()  # assign user.id before backfill queries

    synced_sends = (
        db.query(Send)
        .filter(Send.recipient_phone == phone, Send.recipient_user_id == None)  # noqa: E711
        .update({"recipient_user_id": user.id}, synchronize_session=False)
    )
    db.query(Contact).filter(
        Contact.phone == phone,
        Contact.linked_user_id == None,  # noqa: E711
    ).update({"linked_user_id": user.id}, synchronize_session=False)

    db.commit()
    db.refresh(user)

    if synced_sends:
        logger.info("Backfilled %d send(s) for new user %d (%s)", synced_sends, user.id, phone)

    return user


def _authenticate(db: Session, phone: str, password: str) -> User:
    """Shared auth logic for both login endpoints."""
    try:
        normalized = normalize_phone(phone)
    except ValueError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid phone or password")
    user = db.query(User).filter(User.phone == normalized).first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid phone or password")
    return user


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """JSON login — used by the React frontend."""
    user = _authenticate(db, payload.phone, payload.password)
    token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.post("/token", response_model=TokenResponse)
def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """OAuth2-compatible form login — used by Swagger UI's Authorize button.

    Note: OAuth2 spec uses 'username' field, but we treat it as the phone number.
    """
    user = _authenticate(db, form_data.username, form_data.password)
    token = create_access_token(subject=str(user.id))
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))
