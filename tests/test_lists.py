"""Tests for /lists CRUD endpoints."""


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _create_list(client, token, title="Shopping", items=None):
    if items is None:
        items = [{"custom_product_name": "Widget", "quantity": 2}]
    return client.post("/lists", json={"title": title, "items": items}, headers=auth(token))


# ── create ────────────────────────────────────────────────────────────────────

def test_create_list(client, manager_token):
    r = _create_list(client, manager_token)
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "Shopping"
    assert len(body["items"]) == 1
    assert body["items"][0]["custom_product_name"] == "Widget"
    assert body["items"][0]["quantity"] == 2
    assert body["items"][0]["position"] == 0
    assert "id" in body


def test_create_list_positions_assigned_by_order(client, manager_token):
    items = [
        {"custom_product_name": "First"},
        {"custom_product_name": "Second"},
        {"custom_product_name": "Third"},
    ]
    r = _create_list(client, manager_token, items=items)
    assert r.status_code == 201
    positions = [i["position"] for i in r.json()["items"]]
    assert positions == [0, 1, 2]


def test_create_list_item_requires_product_or_name(client, manager_token):
    """Item with neither product_id nor custom_product_name → 422."""
    r = client.post(
        "/lists",
        json={"items": [{"quantity": 1}]},
        headers=auth(manager_token),
    )
    assert r.status_code == 422


def test_create_list_item_rejects_both_product_and_name(client, manager_token):
    r = client.post(
        "/lists",
        json={"items": [{"product_id": 1, "custom_product_name": "Also this", "quantity": 1}]},
        headers=auth(manager_token),
    )
    assert r.status_code == 422


def test_create_list_empty_items_allowed(client, manager_token):
    r = client.post("/lists", json={"title": "Draft", "items": []}, headers=auth(manager_token))
    assert r.status_code == 201
    assert r.json()["items"] == []


# ── list ──────────────────────────────────────────────────────────────────────

def test_list_ownership_isolation(client, manager_token, buyer_token):
    _create_list(client, manager_token, title="Manager List")
    _create_list(client, buyer_token, title="Buyer List")

    r = client.get("/lists", headers=auth(manager_token))
    assert r.status_code == 200
    titles = [l["title"] for l in r.json()]
    assert "Manager List" in titles
    assert "Buyer List" not in titles


def test_lists_ordered_newest_first(client, manager_token):
    _create_list(client, manager_token, title="First")
    _create_list(client, manager_token, title="Second")
    r = client.get("/lists", headers=auth(manager_token))
    titles = [l["title"] for l in r.json()]
    assert titles[0] == "Second"
    assert titles[1] == "First"


# ── get ───────────────────────────────────────────────────────────────────────

def test_get_list(client, manager_token):
    lid = _create_list(client, manager_token).json()["id"]
    r = client.get(f"/lists/{lid}", headers=auth(manager_token))
    assert r.status_code == 200
    assert r.json()["id"] == lid


def test_get_list_not_owned_returns_404(client, manager_token, buyer_token):
    lid = _create_list(client, manager_token).json()["id"]
    r = client.get(f"/lists/{lid}", headers=auth(buyer_token))
    assert r.status_code == 404


# ── patch ─────────────────────────────────────────────────────────────────────

def test_patch_list_title(client, manager_token):
    lid = _create_list(client, manager_token, title="Old").json()["id"]
    r = client.patch(f"/lists/{lid}", json={"title": "New"}, headers=auth(manager_token))
    assert r.status_code == 200
    assert r.json()["title"] == "New"
    # Items unchanged
    assert len(r.json()["items"]) == 1


def test_patch_list_replaces_items(client, manager_token):
    lid = _create_list(client, manager_token).json()["id"]
    new_items = [
        {"custom_product_name": "Alpha", "quantity": 3},
        {"custom_product_name": "Beta", "quantity": 1},
    ]
    r = client.patch(f"/lists/{lid}", json={"items": new_items}, headers=auth(manager_token))
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 2
    assert items[0]["custom_product_name"] == "Alpha"
    assert items[1]["custom_product_name"] == "Beta"
    assert items[0]["position"] == 0
    assert items[1]["position"] == 1


def test_patch_list_clears_items_with_empty_list(client, manager_token):
    lid = _create_list(client, manager_token).json()["id"]
    r = client.patch(f"/lists/{lid}", json={"items": []}, headers=auth(manager_token))
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_patch_list_not_owned_returns_404(client, manager_token, buyer_token):
    lid = _create_list(client, manager_token).json()["id"]
    r = client.patch(f"/lists/{lid}", json={"title": "Hacked"}, headers=auth(buyer_token))
    assert r.status_code == 404


# ── delete ────────────────────────────────────────────────────────────────────

def test_delete_list(client, manager_token):
    lid = _create_list(client, manager_token).json()["id"]
    r = client.delete(f"/lists/{lid}", headers=auth(manager_token))
    assert r.status_code == 204
    assert client.get(f"/lists/{lid}", headers=auth(manager_token)).status_code == 404


def test_delete_list_not_owned_returns_404(client, manager_token, buyer_token):
    lid = _create_list(client, manager_token).json()["id"]
    r = client.delete(f"/lists/{lid}", headers=auth(buyer_token))
    assert r.status_code == 404
