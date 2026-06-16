"""Tests for per-list item CRUD and has_been_sent signal."""


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create_list(client, token, title="Test List", items=None):
    if items is None:
        items = []
    return client.post("/lists", json={"title": title, "items": items}, headers=auth(token))


def _add_item(client, token, list_id, **kwargs):
    payload = {"quantity": 1, **kwargs}
    return client.post(f"/lists/{list_id}/items", json=payload, headers=auth(token))


# ── POST /lists/{id}/items ───────────────────────────────────────────────────

def test_add_custom_item(client, manager_token):
    lid = _create_list(client, manager_token).json()["id"]
    r = _add_item(client, manager_token, lid, custom_product_name="Widget", quantity=3)
    assert r.status_code == 201
    body = r.json()
    assert body["custom_product_name"] == "Widget"
    assert body["quantity"] == 3
    assert body["position"] == 0  # first item gets position 0


def test_add_item_position_increments(client, manager_token):
    lid = _create_list(client, manager_token, items=[
        {"custom_product_name": "A"},
        {"custom_product_name": "B"},
    ]).json()["id"]
    r = _add_item(client, manager_token, lid, custom_product_name="C")
    assert r.status_code == 201
    assert r.json()["position"] == 2


def test_add_item_to_wrong_list_returns_404(client, manager_token, buyer_token):
    lid = _create_list(client, manager_token).json()["id"]
    r = _add_item(client, buyer_token, lid, custom_product_name="Hacked")
    assert r.status_code == 404


def test_add_item_requires_product_or_name(client, manager_token):
    lid = _create_list(client, manager_token).json()["id"]
    r = client.post(f"/lists/{lid}/items", json={"quantity": 1}, headers=auth(manager_token))
    assert r.status_code == 422


def test_add_item_rejects_both_product_and_name(client, manager_token):
    lid = _create_list(client, manager_token).json()["id"]
    r = client.post(
        f"/lists/{lid}/items",
        json={"product_id": 999, "custom_product_name": "Also this", "quantity": 1},
        headers=auth(manager_token),
    )
    assert r.status_code == 422


def test_added_item_appears_in_list(client, manager_token):
    lid = _create_list(client, manager_token).json()["id"]
    _add_item(client, manager_token, lid, custom_product_name="Banana", quantity=5)
    r = client.get(f"/lists/{lid}", headers=auth(manager_token))
    items = r.json()["items"]
    assert len(items) == 1
    assert items[0]["custom_product_name"] == "Banana"
    assert items[0]["quantity"] == 5


# ── PATCH /lists/{id}/items/{item_id} ───────────────────────────────────────

def test_update_item_quantity(client, manager_token):
    lid = _create_list(client, manager_token, items=[{"custom_product_name": "Milk"}]).json()["id"]
    item_id = client.get(f"/lists/{lid}", headers=auth(manager_token)).json()["items"][0]["id"]
    r = client.patch(f"/lists/{lid}/items/{item_id}", json={"quantity": 7}, headers=auth(manager_token))
    assert r.status_code == 200
    assert r.json()["quantity"] == 7


def test_update_item_rejects_zero_quantity(client, manager_token):
    lid = _create_list(client, manager_token, items=[{"custom_product_name": "Milk"}]).json()["id"]
    item_id = client.get(f"/lists/{lid}", headers=auth(manager_token)).json()["items"][0]["id"]
    r = client.patch(f"/lists/{lid}/items/{item_id}", json={"quantity": 0}, headers=auth(manager_token))
    assert r.status_code == 422


def test_update_item_wrong_owner_returns_404(client, manager_token, buyer_token):
    lid = _create_list(client, manager_token, items=[{"custom_product_name": "Milk"}]).json()["id"]
    item_id = client.get(f"/lists/{lid}", headers=auth(manager_token)).json()["items"][0]["id"]
    r = client.patch(f"/lists/{lid}/items/{item_id}", json={"quantity": 7}, headers=auth(buyer_token))
    assert r.status_code == 404


def test_update_item_wrong_list_returns_404(client, manager_token):
    lid = _create_list(client, manager_token, items=[{"custom_product_name": "Milk"}]).json()["id"]
    lid2 = _create_list(client, manager_token, title="Other").json()["id"]
    item_id = client.get(f"/lists/{lid}", headers=auth(manager_token)).json()["items"][0]["id"]
    # item belongs to lid, not lid2
    r = client.patch(f"/lists/{lid2}/items/{item_id}", json={"quantity": 2}, headers=auth(manager_token))
    assert r.status_code == 404


# ── DELETE /lists/{id}/items/{item_id} ──────────────────────────────────────

def test_delete_item(client, manager_token):
    lid = _create_list(client, manager_token, items=[
        {"custom_product_name": "A"},
        {"custom_product_name": "B"},
    ]).json()["id"]
    items = client.get(f"/lists/{lid}", headers=auth(manager_token)).json()["items"]
    item_id = items[0]["id"]
    r = client.delete(f"/lists/{lid}/items/{item_id}", headers=auth(manager_token))
    assert r.status_code == 204
    remaining = client.get(f"/lists/{lid}", headers=auth(manager_token)).json()["items"]
    assert len(remaining) == 1
    assert remaining[0]["custom_product_name"] == "B"


def test_delete_item_wrong_owner_returns_404(client, manager_token, buyer_token):
    lid = _create_list(client, manager_token, items=[{"custom_product_name": "A"}]).json()["id"]
    item_id = client.get(f"/lists/{lid}", headers=auth(manager_token)).json()["items"][0]["id"]
    r = client.delete(f"/lists/{lid}/items/{item_id}", headers=auth(buyer_token))
    assert r.status_code == 404


def test_delete_item_wrong_list_returns_404(client, manager_token):
    lid = _create_list(client, manager_token, items=[{"custom_product_name": "A"}]).json()["id"]
    lid2 = _create_list(client, manager_token, title="Other").json()["id"]
    item_id = client.get(f"/lists/{lid}", headers=auth(manager_token)).json()["items"][0]["id"]
    r = client.delete(f"/lists/{lid2}/items/{item_id}", headers=auth(manager_token))
    assert r.status_code == 404


def test_delete_nonexistent_item_returns_404(client, manager_token):
    lid = _create_list(client, manager_token).json()["id"]
    r = client.delete(f"/lists/{lid}/items/99999", headers=auth(manager_token))
    assert r.status_code == 404


# ── has_been_sent ─────────────────────────────────────────────────────────────

def test_has_been_sent_false_on_new_list(client, manager_token):
    lid = _create_list(client, manager_token, items=[{"custom_product_name": "A"}]).json()["id"]
    r = client.get(f"/lists/{lid}", headers=auth(manager_token))
    assert r.status_code == 200
    assert r.json()["has_been_sent"] is False


def test_has_been_sent_false_in_list_index(client, manager_token):
    _create_list(client, manager_token, items=[{"custom_product_name": "A"}])
    r = client.get("/lists", headers=auth(manager_token))
    assert all(l["has_been_sent"] is False for l in r.json())


def test_has_been_sent_true_after_send(client, manager_token, buyer_token):
    from tests.conftest import register_user
    register_user(client, "Supplier", "5553330001")
    lid = _create_list(client, manager_token, items=[{"custom_product_name": "A"}]).json()["id"]
    client.post(
        f"/lists/{lid}/send",
        json={"recipients": [{"phone": "5553330001"}]},
        headers=auth(manager_token),
    )
    r = client.get(f"/lists/{lid}", headers=auth(manager_token))
    assert r.json()["has_been_sent"] is True


def test_has_been_sent_true_in_list_index_after_send(client, manager_token, buyer_token):
    from tests.conftest import register_user
    register_user(client, "Supplier", "5553330002")
    lid = _create_list(client, manager_token, items=[{"custom_product_name": "A"}]).json()["id"]
    client.post(
        f"/lists/{lid}/send",
        json={"recipients": [{"phone": "5553330002"}]},
        headers=auth(manager_token),
    )
    lists = client.get("/lists", headers=auth(manager_token)).json()
    sent_list = next(l for l in lists if l["id"] == lid)
    assert sent_list["has_been_sent"] is True
