"""Tests for per-user running-low product flags and auto-clear on received."""


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ─── helpers ──────────────────────────────────────────────────────────────────

def _make_product(client, token, name="Widget"):
    r = client.post(
        "/products",
        json={"name": name, "category": "other"},
        headers=auth(token),
    )
    assert r.status_code == 201
    return r.json()


def _register(client, name, phone, password="password123"):
    client.post("/auth/request-code", json={"phone": phone})
    client.post("/auth/register", json={
        "name": name, "phone": phone, "password": password, "code": "000000"
    })
    r = client.post("/auth/login", json={"phone": phone, "password": password})
    return r.json()["access_token"]


def _make_list_with_product(client, token, product_id, qty=2):
    r = client.post(
        "/lists",
        json={"items": [{"product_id": product_id, "quantity": qty}]},
        headers=auth(token),
    )
    assert r.status_code == 201
    return r.json()


def _send_list(client, token, list_id, recipient_phone):
    r = client.post(
        f"/lists/{list_id}/send",
        json={"recipients": [{"phone": recipient_phone}]},
        headers=auth(token),
    )
    assert r.status_code == 201
    return r.json()[0]


# ─── flag / unflag / list ─────────────────────────────────────────────────────

def test_flag_product_low(client, manager_token):
    p = _make_product(client, manager_token)
    r = client.post(f"/products/{p['id']}/low", headers=auth(manager_token))
    assert r.status_code == 200
    assert r.json()["is_low"] is True


def test_flag_idempotent(client, manager_token):
    """Flagging an already-flagged product is a no-op and returns 200."""
    p = _make_product(client, manager_token)
    client.post(f"/products/{p['id']}/low", headers=auth(manager_token))
    r = client.post(f"/products/{p['id']}/low", headers=auth(manager_token))
    assert r.status_code == 200


def test_unflag_product(client, manager_token):
    p = _make_product(client, manager_token)
    client.post(f"/products/{p['id']}/low", headers=auth(manager_token))
    r = client.delete(f"/products/{p['id']}/low", headers=auth(manager_token))
    assert r.status_code == 204


def test_unflag_nonexistent_is_noop(client, manager_token):
    """Unflaging a product that isn't flagged doesn't error."""
    p = _make_product(client, manager_token)
    r = client.delete(f"/products/{p['id']}/low", headers=auth(manager_token))
    assert r.status_code == 204


def test_get_low_products_empty(client, manager_token):
    r = client.get("/products/low", headers=auth(manager_token))
    assert r.status_code == 200
    assert r.json() == []


def test_get_low_products_returns_flagged(client, manager_token):
    p1 = _make_product(client, manager_token, "Widget A")
    p2 = _make_product(client, manager_token, "Widget B")
    client.post(f"/products/{p1['id']}/low", headers=auth(manager_token))
    client.post(f"/products/{p2['id']}/low", headers=auth(manager_token))

    r = client.get("/products/low", headers=auth(manager_token))
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()}
    assert p1["id"] in ids
    assert p2["id"] in ids


def test_low_flag_is_per_user(client, manager_token, buyer_token):
    """One user's flags don't appear in another user's list."""
    p = _make_product(client, manager_token)
    client.post(f"/products/{p['id']}/low", headers=auth(manager_token))

    r = client.get("/products/low", headers=auth(buyer_token))
    assert r.json() == []


def test_flag_nonexistent_product_returns_404(client, manager_token):
    r = client.post("/products/99999/low", headers=auth(manager_token))
    assert r.status_code == 404


def test_unauthenticated_cannot_flag(client):
    r = client.post("/products/1/low")
    assert r.status_code == 401


# ─── is_low in search results ─────────────────────────────────────────────────

def test_search_includes_is_low(client, manager_token):
    p = _make_product(client, manager_token, "SpecialGadget")
    client.post(f"/products/{p['id']}/low", headers=auth(manager_token))

    r = client.get("/products?search=SpecialGadget", headers=auth(manager_token))
    assert r.status_code == 200
    results = r.json()
    found = next((x for x in results if x["id"] == p["id"]), None)
    assert found is not None
    assert found["is_low"] is True


def test_search_is_low_false_when_not_flagged(client, manager_token):
    p = _make_product(client, manager_token, "UnflaggedWidget")
    r = client.get("/products?search=UnflaggedWidget", headers=auth(manager_token))
    assert r.status_code == 200
    results = r.json()
    found = next((x for x in results if x["id"] == p["id"]), None)
    assert found is not None
    assert found["is_low"] is False


# ─── auto-unflag on received ──────────────────────────────────────────────────

def test_auto_unflag_on_check_off(client, manager_token, buyer_token):
    """Checking off an item (recipient side) clears the owner's low flag."""
    p = _make_product(client, manager_token, "AutoWidget")
    # Owner flags the product
    client.post(f"/products/{p['id']}/low", headers=auth(manager_token))

    lst = _make_list_with_product(client, manager_token, p["id"])
    send = _send_list(client, manager_token, lst["id"], "5552220001")
    item_id = lst["items"][0]["id"]

    # Recipient checks off the item
    r = client.patch(
        f"/sends/{send['id']}/items/{item_id}",
        json={"checked": True},
        headers=auth(buyer_token),
    )
    assert r.status_code == 200

    # Owner's flag should now be gone
    r = client.get("/products/low", headers=auth(manager_token))
    ids = {x["id"] for x in r.json()}
    assert p["id"] not in ids


def test_auto_unflag_on_mark_all_received(client, manager_token, buyer_token):
    """mark-all-received clears the owner's low flags for all list products."""
    p1 = _make_product(client, manager_token, "BulkA")
    p2 = _make_product(client, manager_token, "BulkB")
    client.post(f"/products/{p1['id']}/low", headers=auth(manager_token))
    client.post(f"/products/{p2['id']}/low", headers=auth(manager_token))

    r = client.post(
        "/lists",
        json={"items": [
            {"product_id": p1["id"], "quantity": 1},
            {"product_id": p2["id"], "quantity": 1},
        ]},
        headers=auth(manager_token),
    )
    lst = r.json()
    send = _send_list(client, manager_token, lst["id"], "5552220001")

    client.post(f"/sends/{send['id']}/mark-all-received", headers=auth(buyer_token))

    r = client.get("/products/low", headers=auth(manager_token))
    assert r.json() == []


def test_auto_unflag_custom_item_does_not_error(client, manager_token, buyer_token):
    """Custom-name items have no product_id; checking them off must not error."""
    r = client.post(
        "/lists",
        json={"items": [{"custom_product_name": "Mystery Box", "quantity": 1}]},
        headers=auth(manager_token),
    )
    lst = r.json()
    send = _send_list(client, manager_token, lst["id"], "5552220001")
    item_id = lst["items"][0]["id"]

    r = client.patch(
        f"/sends/{send['id']}/items/{item_id}",
        json={"checked": True},
        headers=auth(buyer_token),
    )
    assert r.status_code == 200


def test_auto_unflag_clears_only_owner_flag_not_others(client, manager_token, buyer_token):
    """Checking an item clears the list owner's flag, not another user's."""
    p = _make_product(client, manager_token, "SharedProduct")
    # Both owner and buyer flag the product
    client.post(f"/products/{p['id']}/low", headers=auth(manager_token))
    client.post(f"/products/{p['id']}/low", headers=auth(buyer_token))

    lst = _make_list_with_product(client, manager_token, p["id"])
    send = _send_list(client, manager_token, lst["id"], "5552220001")
    item_id = lst["items"][0]["id"]

    client.patch(
        f"/sends/{send['id']}/items/{item_id}",
        json={"checked": True},
        headers=auth(buyer_token),
    )

    # Owner's flag is cleared
    r = client.get("/products/low", headers=auth(manager_token))
    assert not any(x["id"] == p["id"] for x in r.json())

    # Buyer's own flag is NOT cleared (buyer is the recipient, not the list owner)
    r = client.get("/products/low", headers=auth(buyer_token))
    assert any(x["id"] == p["id"] for x in r.json())
