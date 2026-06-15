"""Tests for the send action, wa_link builder, inbox, and item check-off."""
import pytest

from app.services.whatsapp import build_wa_link, format_list_body


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ─── helpers ──────────────────────────────────────────────────────────────────

def _make_list(client, token, title="My List", items=None):
    if items is None:
        items = [{"custom_product_name": "Widget", "quantity": 1}]
    r = client.post("/lists", json={"title": title, "items": items}, headers=auth(token))
    assert r.status_code == 201
    return r.json()


def _register(client, name, phone, password="password123"):
    client.post("/auth/request-code", json={"phone": phone})
    client.post("/auth/register", json={"name": name, "phone": phone, "password": password, "code": "000000"})
    r = client.post("/auth/login", json={"phone": phone, "password": password})
    return r.json()["access_token"]


# ─── whatsapp helper unit tests ───────────────────────────────────────────────

def test_build_wa_link_basic():
    link = build_wa_link("+16467522092", "Hello World")
    assert link == "https://wa.me/16467522092?text=Hello%20World"


def test_build_wa_link_encodes_special_chars():
    link = build_wa_link("+16467522092", "A & B\nLine2")
    assert link.startswith("https://wa.me/16467522092?text=")
    assert "A" in link
    assert "%26" in link   # & → %26
    assert "%0A" in link   # \n → %0A


def test_build_wa_link_strips_plus():
    link = build_wa_link("+12025550001", "Hi")
    assert link.startswith("https://wa.me/12025550001?text=")


# ─── send to contact ──────────────────────────────────────────────────────────

def test_send_to_contact(client, manager_token):
    lst = _make_list(client, manager_token)
    # Save a contact
    c_r = client.post(
        "/contacts",
        json={"nickname": "Alice", "phone": "6467522092"},
        headers=auth(manager_token),
    )
    contact_id = c_r.json()["id"]

    r = client.post(
        f"/lists/{lst['id']}/send",
        json={"recipients": [{"contact_id": contact_id}]},
        headers=auth(manager_token),
    )
    assert r.status_code == 201
    sends = r.json()
    assert len(sends) == 1
    assert sends[0]["contact_id"] == contact_id
    assert sends[0]["recipient_phone"] == "+16467522092"


# ─── send to raw external number ──────────────────────────────────────────────

def test_send_external_number_returns_wa_link(client, manager_token):
    lst = _make_list(client, manager_token)
    r = client.post(
        f"/lists/{lst['id']}/send",
        json={"recipients": [{"phone": "6467522092"}]},
        headers=auth(manager_token),
    )
    assert r.status_code == 201
    send = r.json()[0]
    assert send["recipient_user_id"] is None
    assert send["wa_link"] is not None
    assert "wa.me" in send["wa_link"]
    assert "16467522092" in send["wa_link"]


def test_wa_link_not_returned_for_in_system_recipient(client, manager_token, buyer_token):
    """Sending to a registered user → wa_link is null."""
    lst = _make_list(client, manager_token)
    # buyer_token user has phone "5552220001" → stored as "+15552220001"
    r = client.post(
        f"/lists/{lst['id']}/send",
        json={"recipients": [{"phone": "5552220001"}]},
        headers=auth(manager_token),
    )
    assert r.status_code == 201
    send = r.json()[0]
    assert send["recipient_user_id"] is not None
    assert send["wa_link"] is None


# ─── send to registered user sets recipient_user_id ───────────────────────────

def test_send_to_registered_user_sets_recipient_user_id(client, manager_token, buyer_token):
    lst = _make_list(client, manager_token)
    r = client.post(
        f"/lists/{lst['id']}/send",
        json={"recipients": [{"phone": "5552220001"}]},
        headers=auth(manager_token),
    )
    assert r.status_code == 201
    send = r.json()[0]
    assert send["recipient_user_id"] is not None
    assert send["recipient_phone"] == "+15552220001"


# ─── inbox ────────────────────────────────────────────────────────────────────

def test_send_appears_in_recipient_inbox(client, manager_token, buyer_token):
    lst = _make_list(client, manager_token)
    client.post(
        f"/lists/{lst['id']}/send",
        json={"recipients": [{"phone": "5552220001"}]},
        headers=auth(manager_token),
    )

    inbox = client.get("/inbox", headers=auth(buyer_token)).json()
    assert len(inbox) == 1
    assert inbox[0]["list_id"] == lst["id"]
    assert len(inbox[0]["item_states"]) == 1


def test_inbox_includes_list_title_and_items(client, manager_token, buyer_token):
    """GET /inbox must return list_title and items with names and quantities."""
    lst = _make_list(
        client,
        manager_token,
        title="Test Restock",
        items=[
            {"custom_product_name": "Widget A", "quantity": 3},
            {"custom_product_name": "Widget B", "quantity": 1},
        ],
    )
    client.post(
        f"/lists/{lst['id']}/send",
        json={"recipients": [{"phone": "5552220001"}]},
        headers=auth(manager_token),
    )

    inbox = client.get("/inbox", headers=auth(buyer_token)).json()
    assert len(inbox) == 1
    send = inbox[0]

    assert send["list_title"] == "Test Restock"

    assert len(send["items"]) == 2
    by_name = {item["custom_product_name"]: item for item in send["items"]}
    assert "Widget A" in by_name
    assert "Widget B" in by_name
    assert by_name["Widget A"]["quantity"] == 3
    assert by_name["Widget B"]["quantity"] == 1

    assert len(send["item_states"]) == 2


def test_sender_does_not_see_send_in_own_inbox(client, manager_token, buyer_token):
    lst = _make_list(client, manager_token)
    client.post(
        f"/lists/{lst['id']}/send",
        json={"recipients": [{"phone": "5552220001"}]},
        headers=auth(manager_token),
    )
    manager_inbox = client.get("/inbox", headers=auth(manager_token)).json()
    assert manager_inbox == []


# ─── two-recipient independence ───────────────────────────────────────────────

def test_two_recipients_create_independent_sends(client, manager_token, buyer_token):
    r2_token = _register(client, "R2", "6467522092")
    lst = _make_list(client, manager_token)

    r = client.post(
        f"/lists/{lst['id']}/send",
        json={"recipients": [{"phone": "5552220001"}, {"phone": "6467522092"}]},
        headers=auth(manager_token),
    )
    assert r.status_code == 201
    sends = r.json()
    assert len(sends) == 2
    assert sends[0]["id"] != sends[1]["id"]
    # Both have independent item_state lists (same list_item_id, separate send rows)
    assert len(sends[0]["item_states"]) == 1
    assert len(sends[1]["item_states"]) == 1


def test_checkoff_does_not_affect_other_send(client, manager_token, buyer_token):
    """Checking off an item in send A must not change send B's state."""
    r2_token = _register(client, "R2", "6467522092")
    lst = _make_list(client, manager_token)
    item_id = lst["items"][0]["id"]

    sends_r = client.post(
        f"/lists/{lst['id']}/send",
        json={"recipients": [{"phone": "5552220001"}, {"phone": "6467522092"}]},
        headers=auth(manager_token),
    )
    send_a_id = sends_r.json()[0]["id"]
    send_b_id = sends_r.json()[1]["id"]

    # Buyer (recipient of send A) checks off the item
    patch_r = client.patch(
        f"/sends/{send_a_id}/items/{item_id}",
        json={"checked": True},
        headers=auth(buyer_token),
    )
    assert patch_r.status_code == 200
    assert patch_r.json()["checked"] is True

    # Send B's inbox for R2 must still show unchecked
    r2_inbox = client.get("/inbox", headers=auth(r2_token)).json()
    send_b = next(s for s in r2_inbox if s["id"] == send_b_id)
    assert all(not state["checked"] for state in send_b["item_states"])


# ─── check-off permissions ────────────────────────────────────────────────────

def test_checkoff_by_recipient_allowed(client, manager_token, buyer_token):
    lst = _make_list(client, manager_token)
    item_id = lst["items"][0]["id"]
    send_r = client.post(
        f"/lists/{lst['id']}/send",
        json={"recipients": [{"phone": "5552220001"}]},
        headers=auth(manager_token),
    )
    send_id = send_r.json()[0]["id"]

    r = client.patch(
        f"/sends/{send_id}/items/{item_id}",
        json={"checked": True},
        headers=auth(buyer_token),
    )
    assert r.status_code == 200
    assert r.json()["checked"] is True


def test_checkoff_by_list_owner_allowed(client, manager_token, buyer_token):
    lst = _make_list(client, manager_token)
    item_id = lst["items"][0]["id"]
    send_r = client.post(
        f"/lists/{lst['id']}/send",
        json={"recipients": [{"phone": "5552220001"}]},
        headers=auth(manager_token),
    )
    send_id = send_r.json()[0]["id"]

    r = client.patch(
        f"/sends/{send_id}/items/{item_id}",
        json={"checked": True},
        headers=auth(manager_token),
    )
    assert r.status_code == 200
    assert r.json()["checked"] is True


def test_checkoff_by_third_party_returns_403(client, manager_token, buyer_token):
    third_token = _register(client, "Third", "6467522092")
    lst = _make_list(client, manager_token)
    item_id = lst["items"][0]["id"]
    send_r = client.post(
        f"/lists/{lst['id']}/send",
        json={"recipients": [{"phone": "5552220001"}]},
        headers=auth(manager_token),
    )
    send_id = send_r.json()[0]["id"]

    r = client.patch(
        f"/sends/{send_id}/items/{item_id}",
        json={"checked": True},
        headers=auth(third_token),
    )
    assert r.status_code == 403
