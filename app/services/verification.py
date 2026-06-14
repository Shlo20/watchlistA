"""Phone verification: generate, store, and validate one-time codes."""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.verification import PhoneVerification

logger = logging.getLogger(__name__)

_DEV_CODE = "000000"
_CODE_TTL_MINUTES = 10


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def send_verification_code(phone: str, db: Session) -> None:
    """Generate a 6-digit OTP, store it hashed, and (optionally) send via SMS."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    now = datetime.utcnow()
    record = PhoneVerification(
        phone=phone,
        code_hash=_hash_code(code),
        expires_at=now + timedelta(minutes=_CODE_TTL_MINUTES),
        consumed=False,
        created_at=now,
    )
    db.add(record)
    db.commit()

    if settings.sms_verification_enabled:
        # SWAP POINT: real OTP sender (Twilio Verify / Firebase) goes here
        # e.g. twilio_client.verify.v2.services(VERIFY_SID).verifications.create(to=phone, channel="sms")
        pass
    # else: dev/test mode — no SMS sent; callers use the fixed dev code "000000"


def verify_code(phone: str, code: str, db: Session) -> bool:
    """Return True and mark the code consumed if it is valid; False otherwise."""
    now = datetime.utcnow()
    record = (
        db.query(PhoneVerification)
        .filter(
            PhoneVerification.phone == phone,
            PhoneVerification.consumed == False,  # noqa: E712
        )
        .order_by(PhoneVerification.created_at.desc())
        .first()
    )

    if record is None:
        return False

    if record.expires_at < now:
        return False

    # Dev-only shortcut: "000000" is accepted without hash check when SMS is disabled.
    # A valid (non-expired, unconsumed) record must still exist so the full request-code
    # → register flow is exercised even in development.
    if not settings.sms_verification_enabled and code == _DEV_CODE:
        record.consumed = True
        db.commit()
        return True

    if record.code_hash != _hash_code(code):
        return False

    record.consumed = True
    db.commit()
    return True
