"""Tests for business-name branding on wa messages, inbox, and header."""
from urllib.parse import unquote

from app.services.whatsapp import format_list_body, format_priced_body


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ─── helpers ──────────────────────────────────────────────────────────────────

def _register_with_biz(client, name, phone, business_name, password="password123"):
    client.post("/auth/request-code", json={"phone": phone})
    client.post("/auth/register", json={
        "name": name, "phone": phone, "password": password, "code": "000000"
    })
    token = client.post("/auth/login", json={"phone": phone, "password": password}).json()["access_token"]
    # Set business name via PATCH /auth/me
    client.patch("/auth/me", json={"business_name": business_name}, headers=auth(token))
    return token


def _make_list(client, token, title="Order", items=None):
    if items is None:
        items = [{"custom_product_name": "Widget", "quantity": 2}]
    r = client.post("/lists", json={"title": title, "items": items}, headers=auth(token))
    assert r.status_code == 201
    return r.json()


# ─── format_list_body unit tests ──────────────────────────────────────────────

def test_format_list_body_with_business_name():
    class _Lst:
        title = "Restock"

    class _Item:
        product = None
        custom_product_name = "Widget"
        quantity = 3

    body = format_list_body(_Lst(), [_Item()], business_name="Acme Corp")
    lines = body.split("\n")
    assert lines[0] == "Order from Acme Corp"
    assert lines[1] == ""   # blank separator
    assert "*Restock*" in body
    assert "Widget" in body


def test_format_list_body_no_business_name_unchanged():
    class _Lst:
        title = "Restock"

    class _Item:
        product = None
        custom_product_name = "Widget"
        quantity = 1

    body = format_list_body(_Lst(), [_Item()])
    assert "Order from" not in body
    assert body.startswith("*Restock*")


def test_format_list_body_empty_string_business_name_omitted():
    class _Lst:
        title = "Restock"

    class _Item:
        product = None
        custom_product_name = "Widget"
        quantity = 1

    body = format_list_body(_Lst(), [_Item()], business_name="")
    assert "Order from" not in body


# ─── format_priced_body unit tests ────────────────────────────────────────────

def test_format_priced_body_with_business_name():
    class _Lst:
        title = "Quote"

    class _Item:
        id = 1
        product = None
        custom_product_name = "Gadget"
        quantity = 2

    body = format_priced_body(_Lst(), [_Item()], {1: 500}, business_name="My Biz")
    lines = body.split("\n")
    assert lines[0] == "Order from My Biz"
    assert lines[1] == ""
    assert "Total" in body


def test_format_priced_body_no_business_name_unchanged():
    class _Lst:
        title = "Quote"

    class _Item:
        id = 1
        product = None
        custom_product_name = "Gadget"
        quantity = 1

    body = format_priced_body(_Lst(), [_Item()], {1: 300})
    assert "Order from" not in body


def test_format_priced_body_empty_string_omitted():
    class _Lst:
        title = "Quote"

    class _Item:
        id = 1
        product = None
        custom_product_name = "Gadget"
        quantity = 1

    body = format_priced_body(_Lst(), [_Item()], {}, business_name="")
    assert "Order from" not in body


# ─── send wa-link includes business name ──────────────────────────────────────

def test_send_wa_link_includes_business_name(client, buyer_token):
    """When the sender has a business_name, the wa_link body includes 'Order from X'."""
    manager_token = _register_with_biz(client, "Mgr", "9990000001", "Acme Corp")
    lst = _make_list(client, manager_token)

    r = client.post(
        f"/lists/{lst['id']}/send",
        json={"recipients": [{"phone": "5552220001", "to_whatsapp": True}]},
        headers=auth(manager_token),
    )
    assert r.status_code == 201
    wa_link = r.json()[0]["wa_link"]
    assert wa_link is not None
    decoded = unquote(wa_link)
    assert "Order from Acme Corp" in decoded


def test_send_wa_link_no_business_name_no_header(client, buyer_token):
    """No business_name → no 'Order from' header in wa link."""
    # manager_token fixture has no business_name set
    lst = _make_list(client, buyer_token)
    r = client.post(
        f"/lists/{lst['id']}/send",
        json={"recipients": [{"phone": "9990001234"}]},
        headers=auth(buyer_token),
    )
    assert r.status_code == 201
    wa_link = r.json()[0]["wa_link"]
    assert wa_link is not None
    assert "Order+from" not in wa_link
    assert "Order%20from" not in wa_link


# ─── inbox sender_business_name ───────────────────────────────────────────────

def test_inbox_includes_sender_business_name(client, buyer_token):
    """Inbox payload carries sender_business_name when sender has one."""
    manager_token = _register_with_biz(client, "Mgr2", "9990000002", "Best Biz")
    lst = _make_list(client, manager_token)

    client.post(
        f"/lists/{lst['id']}/send",
        json={"recipients": [{"phone": "5552220001"}]},
        headers=auth(manager_token),
    )

    r = client.get("/inbox", headers=auth(buyer_token))
    assert r.status_code == 200
    sends = r.json()
    assert len(sends) >= 1
    # Find the one from our manager
    matching = [s for s in sends if s["sender_business_name"] == "Best Biz"]
    assert len(matching) == 1


def test_inbox_sender_business_name_null_when_not_set(client, manager_token, buyer_token):
    """sender_business_name is null when the sender has no business_name."""
    lst = _make_list(client, manager_token)
    client.post(
        f"/lists/{lst['id']}/send",
        json={"recipients": [{"phone": "5552220001"}]},
        headers=auth(manager_token),
    )

    r = client.get("/inbox", headers=auth(buyer_token))
    assert r.status_code == 200
    sends = r.json()
    assert len(sends) >= 1
    assert sends[0]["sender_business_name"] is None


# ─── quote wa-link includes caller's business name ────────────────────────────

def test_quote_wa_link_includes_supplier_business_name(client, manager_token):
    """Supplier calls quote-wa-link → body has supplier's business_name."""
    buyer_token = _register_with_biz(client, "Supplier", "9990000003", "Supplier Co")
    lst = _make_list(client, manager_token)
    r = client.post(
        f"/lists/{lst['id']}/send",
        json={"recipients": [{"phone": "9990000003"}]},
        headers=auth(manager_token),
    )
    assert r.status_code == 201
    send_id = r.json()[0]["id"]
    item_id = lst["items"][0]["id"]

    client.patch(f"/sends/{send_id}/items/{item_id}", json={"unit_price_cents": 400}, headers=auth(buyer_token))
    client.post(f"/sends/{send_id}/submit-quote", headers=auth(buyer_token))

    r = client.get(f"/sends/{send_id}/quote-wa-link", headers=auth(buyer_token))
    assert r.status_code == 200
    decoded = unquote(r.json()["wa_link"])
    assert "Order from Supplier Co" in decoded


def test_quote_wa_link_owner_includes_owner_business_name(client, buyer_token):
    """Owner calls quote-wa-link → body has owner's business_name."""
    manager_token = _register_with_biz(client, "Owner", "9990000004", "Owner Biz")
    lst = _make_list(client, manager_token)
    r = client.post(
        f"/lists/{lst['id']}/send",
        json={"recipients": [{"phone": "5552220001"}]},
        headers=auth(manager_token),
    )
    send_id = r.json()[0]["id"]
    client.post(f"/sends/{send_id}/submit-quote", headers=auth(buyer_token))

    r = client.get(f"/sends/{send_id}/quote-wa-link", headers=auth(manager_token))
    assert r.status_code == 200
    decoded = unquote(r.json()["wa_link"])
    assert "Order from Owner Biz" in decoded
