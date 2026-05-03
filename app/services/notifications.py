"""SMS notifications via carrier email-to-SMS gateways.

Free alternative to Twilio. Send an email to {phone}@{carrier_gateway} and the
recipient's phone shows it as a text. Swap this module for Twilio later by
re-implementing the two `notify_*` functions.
"""
import logging

import httpx

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.product import Product
from app.models.request import Request
from app.models.user import User, UserRole


logger = logging.getLogger(__name__)


CARRIER_GATEWAYS = {
    "att": "txt.att.net",
    "verizon": "vtext.com",
    "tmobile": "tmomail.net",
    "sprint": "messaging.sprintpcs.com",
    "boost": "sms.myboostmobile.com",
    "cricket": "sms.cricketwireless.net",
}


def _gateway_address(phone: str, carrier: str | None) -> str | None:
    """Build the SMS gateway email address for a phone + carrier."""
    if not carrier:
        return None
    domain = CARRIER_GATEWAYS.get(carrier.lower())
    if not domain:
        return None
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return None
    return f"{digits}@{domain}"


def _send_sms_via_email(to_email: str, body: str) -> bool:
    """Send an email through Resend that gets delivered as an SMS."""
    if not settings.resend_api_key:
        logger.warning("RESEND_API_KEY not configured; skipping notification to %s", to_email)
        return False
    try:
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.notification_from_email,
                "to": [to_email],
                "subject": "",  # carriers ignore subject for SMS
                "text": body,
            },
            timeout=10,
        )
        r.raise_for_status()
        return True
    except httpx.HTTPError as e:
        logger.error("Failed to send notification: %s", e)
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
        urgency_tag = " [URGENT]" if req.urgency.value == "urgent" else ""
        body = f"New restock request{urgency_tag}: {req.quantity}x {product_label}"
        if req.notes:
            body += f"\nNotes: {req.notes}"
        for buyer in buyers:
            addr = _gateway_address(buyer.phone, buyer.carrier)
            if addr:
                _send_sms_via_email(addr, body)
    finally:
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
        addr = _gateway_address(requester.phone, requester.carrier)
        if addr:
            _send_sms_via_email(addr, body)
    finally:
        db.close()
