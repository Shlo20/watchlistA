"""Tests for the two-step phone-verification registration flow and sync-on-register backfill."""
import hashlib
from datetime import datetime, timedelta

from app.models.verification import PhoneVerification
from tests.conftest import register_user


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ─── two-step registration ────────────────────────────────────────────────────

def test_request_code_then_register_succeeds(client):
    r = client.post("/auth/request-code", json={"phone": "4441110001"})
    assert r.status_code == 200
    assert "message" in r.json()

    r2 = client.post("/auth/register", json={
        "name": "Alice",
        "phone": "4441110001",
        "password": "password123",
        "code": "000000",
    })
    assert r2.status_code == 201
    assert r2.json()["name"] == "Alice"


def test_wrong_code_returns_401(client):
    client.post("/auth/request-code", json={"phone": "4441110002"})
    r = client.post("/auth/register", json={
        "name": "Alice",
        "phone": "4441110002",
        "password": "password123",
        "code": "999999",  # wrong — not "000000", hash won't match real code either
    })
    assert r.status_code == 401


def test_missing_code_returns_422(client):
    """Registration payload without 'code' field fails schema validation."""
    r = client.post("/auth/register", json={
        "name": "Alice",
        "phone": "4441110003",
        "password": "password123",
        # code intentionally omitted
    })
    assert r.status_code == 422


def test_expired_code_rejected(client, db_session):
    """A code past its 10-minute TTL is rejected even in dev mode."""
    session, _ = db_session
    phone = "+14441110004"
    now = datetime.utcnow()
    expired = PhoneVerification(
        phone=phone,
        code_hash=hashlib.sha256(b"000000").hexdigest(),
        expires_at=now - timedelta(seconds=1),  # already expired
        consumed=False,
        created_at=now - timedelta(minutes=11),
    )
    session.add(expired)
    session.commit()

    r = client.post("/auth/register", json={
        "name": "Alice",
        "phone": phone,
        "password": "password123",
        "code": "000000",
    })
    assert r.status_code == 401


def test_reused_code_rejected(client):
    """A code may only be used once; a second attempt without requesting a new code fails."""
    phone = "4441110005"
    client.post("/auth/request-code", json={"phone": phone})
    r1 = client.post("/auth/register", json={
        "name": "Alice",
        "phone": phone,
        "password": "password123",
        "code": "000000",
    })
    assert r1.status_code == 201  # first use: code consumed

    # Second attempt: same (now consumed) record, no new request-code call
    r2 = client.post("/auth/register", json={
        "name": "Alice2",
        "phone": phone,
        "password": "password123",
        "code": "000000",
    })
    # verify_code returns False (no unconsumed record) → 401, before 409 is reached
    assert r2.status_code == 401


# ─── sync-on-register backfill ───────────────────────────────────────────────

def test_backfill_send_visible_in_inbox_after_register(client, manager_token):
    """User A sends to an unregistered number; registering that number reveals the send in inbox."""
    lst = client.post(
        "/lists",
        json={"title": "Backfill Test", "items": [{"custom_product_name": "Widget", "quantity": 1}]},
        headers=auth(manager_token),
    ).json()

    unregistered = "4441110006"
    send_r = client.post(
        f"/lists/{lst['id']}/send",
        json={"recipients": [{"phone": unregistered}]},
        headers=auth(manager_token),
    )
    assert send_r.status_code == 201
    assert send_r.json()[0]["recipient_user_id"] is None  # not yet linked

    # Register the previously-unregistered number
    client.post("/auth/request-code", json={"phone": unregistered})
    reg_r = client.post("/auth/register", json={
        "name": "New User",
        "phone": unregistered,
        "password": "password123",
        "code": "000000",
    })
    assert reg_r.status_code == 201

    # Login as new user and check inbox
    token_r = client.post("/auth/login", json={"phone": unregistered, "password": "password123"})
    new_token = token_r.json()["access_token"]

    inbox = client.get("/inbox", headers=auth(new_token)).json()
    assert len(inbox) == 1
    assert inbox[0]["list_id"] == lst["id"]


def test_backfill_contact_linked_after_register(client, manager_token):
    """When a new user registers, existing contacts with their phone get linked_user_id set."""
    unregistered = "4441110007"

    # Manager saves a contact for the unregistered phone
    c_r = client.post(
        "/contacts",
        json={"nickname": "Future User", "phone": unregistered},
        headers=auth(manager_token),
    )
    assert c_r.status_code == 201
    contact_id = c_r.json()["id"]
    assert c_r.json()["linked_user_id"] is None

    # Register the phone number
    client.post("/auth/request-code", json={"phone": unregistered})
    reg_r = client.post("/auth/register", json={
        "name": "Future User",
        "phone": unregistered,
        "password": "password123",
        "code": "000000",
    })
    assert reg_r.status_code == 201
    new_user_id = reg_r.json()["id"]

    # Verify the contact is now linked
    c_after = client.get(f"/contacts/{contact_id}", headers=auth(manager_token)).json()
    assert c_after["linked_user_id"] == new_user_id
