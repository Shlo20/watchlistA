"""Tests for the quote round-trip: supplier prices a received list and submits."""
from app.services.whatsapp import format_priced_body


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
    client.post("/auth/register", json={
        "name": name, "phone": phone, "password": password, "code": "000000"
    })
    r = client.post("/auth/login", json={"phone": phone, "password": password})
    return r.json()["access_token"]


def _send_to_buyer(client, manager_token, lst):
    r = client.post(
        f"/lists/{lst['id']}/send",
        json={"recipients": [{"phone": "5552220001"}]},
        headers=auth(manager_token),
    )
    assert r.status_code == 201
    return r.json()[0]


# ─── format_priced_body unit tests ────────────────────────────────────────────

def test_format_priced_body_includes_prices_and_total():
    class _Item:
        def __init__(self, id_, name, qty):
            self.id = id_; self.product = None
            self.custom_product_name = name; self.quantity = qty

    class _Lst:
        title = "Restock"

    items = [_Item(1, "Widget", 3), _Item(2, "Gadget", 2)]
    price_map = {1: 300, 2: 500}   # 3*300 + 2*500 = 1900
    body = format_priced_body(_Lst(), items, price_map)
    assert "*Restock*" in body
    assert "$3.00 ea" in body
    assert "$5.00 ea" in body
    assert "Total: $19.00" in body


def test_format_priced_body_no_prices_no_total():
    class _Item:
        def __init__(self, id_, name, qty):
            self.id = id_; self.product = None
            self.custom_product_name = name; self.quantity = qty

    class _Lst:
        title = "List"

    items = [_Item(1, "Widget", 2)]
    body = format_priced_body(_Lst(), items, {})
    assert "Total" not in body
    assert "$" not in body


# ─── set unit price ───────────────────────────────────────────────────────────

def test_set_unit_price(client, manager_token, buyer_token):
    lst = _make_list(client, manager_token)
    send = _send_to_buyer(client, manager_token, lst)
    item_id = lst["items"][0]["id"]

    r = client.patch(
        f"/sends/{send['id']}/items/{item_id}",
        json={"unit_price_cents": 500},
        headers=auth(buyer_token),
    )
    assert r.status_code == 200
    assert r.json()["unit_price_cents"] == 500


def test_set_price_does_not_clear_other_fields(client, manager_token, buyer_token):
    """Setting unit_price_cents must not disturb checked/received_quantity."""
    lst = _make_list(client, manager_token)
    send = _send_to_buyer(client, manager_token, lst)
    item_id = lst["items"][0]["id"]

    client.patch(f"/sends/{send['id']}/items/{item_id}", json={"checked": True}, headers=auth(buyer_token))
    r = client.patch(f"/sends/{send['id']}/items/{item_id}", json={"unit_price_cents": 200}, headers=auth(buyer_token))
    assert r.status_code == 200
    body = r.json()
    assert body["checked"] is True
    assert body["unit_price_cents"] == 200


def test_third_party_cannot_set_price(client, manager_token, buyer_token):
    lst = _make_list(client, manager_token)
    send = _send_to_buyer(client, manager_token, lst)
    item_id = lst["items"][0]["id"]
    third_token = _register(client, "Third", "6467522092")

    r = client.patch(
        f"/sends/{send['id']}/items/{item_id}",
        json={"unit_price_cents": 100},
        headers=auth(third_token),
    )
    assert r.status_code == 403


# ─── submit-quote ─────────────────────────────────────────────────────────────

def test_submit_quote_sets_quoted_at(client, manager_token, buyer_token):
    lst = _make_list(client, manager_token)
    send = _send_to_buyer(client, manager_token, lst)
    item_id = lst["items"][0]["id"]
    client.patch(f"/sends/{send['id']}/items/{item_id}", json={"unit_price_cents": 300}, headers=auth(buyer_token))

    r = client.post(f"/sends/{send['id']}/submit-quote", headers=auth(buyer_token))
    assert r.status_code == 200
    assert r.json()["quoted_at"] is not None


def test_only_recipient_can_submit_quote(client, manager_token, buyer_token):
    lst = _make_list(client, manager_token)
    send = _send_to_buyer(client, manager_token, lst)

    r = client.post(f"/sends/{send['id']}/submit-quote", headers=auth(manager_token))
    assert r.status_code == 403


# ─── owner's quotes view ──────────────────────────────────────────────────────

def test_owner_sees_quote_with_correct_prices_and_total(client, manager_token, buyer_token):
    lst = _make_list(
        client, manager_token,
        items=[
            {"custom_product_name": "Widget", "quantity": 3},
            {"custom_product_name": "Gadget", "quantity": 2},
        ],
    )
    send = _send_to_buyer(client, manager_token, lst)
    item_ids = [i["id"] for i in lst["items"]]

    # 3x Widget @ $3.00 = $9.00, 2x Gadget @ $5.00 = $10.00 → total $19.00
    client.patch(f"/sends/{send['id']}/items/{item_ids[0]}", json={"unit_price_cents": 300}, headers=auth(buyer_token))
    client.patch(f"/sends/{send['id']}/items/{item_ids[1]}", json={"unit_price_cents": 500}, headers=auth(buyer_token))
    client.post(f"/sends/{send['id']}/submit-quote", headers=auth(buyer_token))

    r = client.get(f"/lists/{lst['id']}/quotes", headers=auth(manager_token))
    assert r.status_code == 200
    quotes = r.json()
    assert len(quotes) == 1
    quote = quotes[0]
    assert quote["send_id"] == send["id"]
    assert quote["total_cents"] == 1900

    price_by_item = {item["list_item_id"]: item["unit_price_cents"] for item in quote["items"]}
    assert price_by_item[item_ids[0]] == 300
    assert price_by_item[item_ids[1]] == 500


def test_unsubmitted_send_not_in_quotes(client, manager_token, buyer_token):
    """Prices set but quote not submitted → quote doesn't appear in owner's view."""
    lst = _make_list(client, manager_token)
    send = _send_to_buyer(client, manager_token, lst)
    item_id = lst["items"][0]["id"]
    client.patch(f"/sends/{send['id']}/items/{item_id}", json={"unit_price_cents": 500}, headers=auth(buyer_token))
    # No submit

    r = client.get(f"/lists/{lst['id']}/quotes", headers=auth(manager_token))
    assert r.json() == []


def test_quotes_not_visible_to_non_owner(client, manager_token, buyer_token):
    lst = _make_list(client, manager_token)
    send = _send_to_buyer(client, manager_token, lst)
    client.post(f"/sends/{send['id']}/submit-quote", headers=auth(buyer_token))

    r = client.get(f"/lists/{lst['id']}/quotes", headers=auth(buyer_token))
    assert r.status_code == 404  # buyer doesn't own the list


# ─── priced WhatsApp link ─────────────────────────────────────────────────────

def test_priced_wa_link_includes_prices_and_total(client, manager_token, buyer_token):
    lst = _make_list(
        client, manager_token,
        title="Test Quote",
        items=[{"custom_product_name": "Widget", "quantity": 2}],
    )
    send = _send_to_buyer(client, manager_token, lst)
    item_id = lst["items"][0]["id"]
    client.patch(f"/sends/{send['id']}/items/{item_id}", json={"unit_price_cents": 1000}, headers=auth(buyer_token))
    client.post(f"/sends/{send['id']}/submit-quote", headers=auth(buyer_token))

    r = client.get(f"/sends/{send['id']}/quote-wa-link", headers=auth(buyer_token))
    assert r.status_code == 200
    wa_link = r.json()["wa_link"]
    assert "wa.me" in wa_link
    assert "%24" in wa_link        # $ is URL-encoded as %24
    assert "10.00" in wa_link      # unit price digits appear unencoded
    assert "20.00" in wa_link      # total: 2 * $10.00


def test_owner_can_also_get_quote_wa_link(client, manager_token, buyer_token):
    lst = _make_list(client, manager_token)
    send = _send_to_buyer(client, manager_token, lst)
    client.post(f"/sends/{send['id']}/submit-quote", headers=auth(buyer_token))

    r = client.get(f"/sends/{send['id']}/quote-wa-link", headers=auth(manager_token))
    assert r.status_code == 200
    assert "wa.me" in r.json()["wa_link"]


def test_total_cents_zero_when_no_prices(client, manager_token, buyer_token):
    lst = _make_list(client, manager_token, items=[
        {"custom_product_name": "Widget", "quantity": 3},
    ])
    send = _send_to_buyer(client, manager_token, lst)
    client.post(f"/sends/{send['id']}/submit-quote", headers=auth(buyer_token))

    r = client.get(f"/lists/{lst['id']}/quotes", headers=auth(manager_token))
    assert r.json()[0]["total_cents"] == 0
