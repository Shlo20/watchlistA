"""SMS notifications via carrier email-to-SMS gateways.

Free alternative to Twilio. Send an email to {phone}@{carrier_gateway} and the
recipient's phone shows it as a text. Swap this module for Twilio later by
re-implementing the public `notify_*` functions.
"""
import logging
import httpx
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.request import Request, RequestStatus
from app.models.user import User, UserRole


logger = logging.getLogger(__name__)


CARRIER_GATEWAYS = {
    "att": "txt.att.net",
    "verizon": "vtext.com",
    "tmobile": "tmomail.net",
    "sprint": "messaging.sprintpcs.com",
    "boost": "sms.myboostmobile.com",
    "cricket": "sms.cricketwireless.net",
    "metro": "mymetropcs.com",
    "uscellular": "email.uscc.net",
    "simple": "tmomail.net",        # Simple Mobile uses T-Mobile network
    "mint": "tmomail.net",          # Mint Mobile uses T-Mobile network
    "straighttalk": "vtext.com",    # Straight Talk defaults to Verizon network
}


def _build_sms_email(user) -> str | None:
    """Return the carrier SMS gateway email for a user, or None if not configured."""
    if not user.carrier:
        logger.warning("User %s has no carrier set; skipping SMS", user.id)
        return None
    domain = CARRIER_GATEWAYS.get(user.carrier.lower())
    if not domain:
        logger.warning("Unknown carrier %r for user %s; skipping SMS", user.carrier, user.id)
        return None
    digits = "".join(c for c in user.phone if c.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        logger.warning("Phone %r for user %s is not 10 digits; skipping SMS", user.phone, user.id)
        return None
    return f"{digits}@{domain}"


def _send_sms_via_brevo(to_address: str, body: str) -> bool:
    """Send a plain-text message to a carrier email-to-SMS gateway via Brevo's HTTPS API."""
    if not settings.sms_enabled:
        logger.info("SMS disabled, would have sent to %s: %s", to_address, body[:100])
        return True

    if not settings.brevo_api_key:
        logger.error("BREVO_API_KEY not set, skipping send to %s", to_address)
        return False

    if not settings.brevo_sender_email:
        logger.error("BREVO_SENDER_EMAIL not set, skipping send to %s", to_address)
        return False

    try:
        response = httpx.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={
                "api-key": settings.brevo_api_key,
                "Content-Type": "application/json",
                "accept": "application/json",
            },
            json={
                "sender": {"email": settings.brevo_sender_email, "name": "Watchlist"},
                "to": [{"email": to_address}],
                "subject": "",
                "textContent": body,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        logger.info("SMS sent to %s via Brevo", to_address)
        return True
    except httpx.HTTPStatusError as e:
        logger.error("Brevo API error sending to %s: %s %s", to_address, e.response.status_code, e.response.text)
        return False
    except Exception as e:
        logger.error("Failed to send SMS to %s: %s", to_address, e)
        return False


def _format_product_label(req: Request) -> str:
    if req.product:
        return req.product.name
    return req.custom_product_name or "Unknown product"


def notify_buyers_new_request(request_id: int) -> None:
    """Text every buyer when a new pending request is created."""
    db = SessionLocal()
    try:
        req = db.query(Request).filter(Request.id == request_id).first()
        if not req:
            return
        buyers = db.query(User).filter(User.role == UserRole.BUYER).all()
        product_label = _format_product_label(req)
        body = f"New restock request: {req.quantity}x {product_label}"
        if req.notes:
            body += f"\nNotes: {req.notes}"
        for buyer in buyers:
            addr = _build_sms_email(buyer)
            if addr:
                _send_sms_via_brevo(addr, body)
    finally:
        db.close()


def send_daily_digest(db=None) -> int:
    """Send one SMS to every buyer listing all pending requests.

    Accepts an optional db session so it can be called from an endpoint that
    already has an injected (test-overrideable) session. When called with no
    arguments (e.g. from a scheduler), it opens and closes its own session.

    Returns the number of items in the digest (0 if nothing to send).
    """
    _owned = db is None
    if _owned:
        db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=24)
        pending = (
            db.query(Request)
            .filter(Request.status == RequestStatus.PENDING)
            .order_by(Request.created_at.asc())
            .all()
        )
        if not pending:
            return 0

        lines = []
        for i, req in enumerate(pending, start=1):
            if req.product:
                label = req.product.name
            else:
                label = f"Custom item: {req.custom_product_name or 'Unknown'}"
            line = f"{i}. {req.quantity}x {label}"
            created = req.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            if created < cutoff:
                line = f"[!] {line}"
            lines.append(line)

        count = len(lines)
        body = (
            f"Today's restock list ({count} item{'s' if count != 1 else ''}):\n"
            + "\n".join(lines)
            + "\nOpen the app to confirm what was received."
        )

        buyers = db.query(User).filter(User.role == UserRole.BUYER).all()
        successes = 0
        failures = 0
        for buyer in buyers:
            addr = _build_sms_email(buyer)
            if addr:
                if _send_sms_via_brevo(addr, body):
                    successes += 1
                else:
                    failures += 1

        if successes or failures:
            logger.info("Digest send complete: %d succeeded, %d failed", successes, failures)

        return count
    finally:
        if _owned:
            db.close()


def notify_requester_status_change(request_id: int) -> None:
    """Text the manager who made the request when its status changes."""
    db = SessionLocal()
    try:
        req = db.query(Request).filter(Request.id == request_id).first()
        if not req:
            return
        requester = db.query(User).filter(User.id == req.requester_id).first()
        if not requester:
            return
        product_label = _format_product_label(req)
        body = f"Your request ({req.quantity}x {product_label}) is now: {req.status.value.upper()}"
        addr = _build_sms_email(requester)
        if addr:
            _send_sms_via_brevo(addr, body)
    finally:
        db.close()
