"""Tests for the core request lifecycle — the heart of the app."""


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create_product(client, buyer_token):
    r = client.post(
        "/products",
        json={"name": "iPhone 15 Case", "category": "case", "brand": "Apple"},
        headers=auth_headers(buyer_token),
    )
    assert r.status_code == 201
    return r.json()["id"]


def test_manager_creates_request_with_catalog_product(client, manager_token, buyer_token):
    pid = _create_product(client, buyer_token)
    r = client.post(
        "/requests",
        json={"product_id": pid, "quantity": 5, "urgency": "urgent"},
        headers=auth_headers(manager_token),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert body["quantity"] == 5
    assert body["urgency"] == "urgent"


def test_manager_creates_request_with_custom_name(client, manager_token):
    r = client.post(
        "/requests",
        json={"custom_product_name": "Some new accessory", "quantity": 2},
        headers=auth_headers(manager_token),
    )
    assert r.status_code == 201
    assert r.json()["custom_product_name"] == "Some new accessory"


def test_request_rejects_both_product_id_and_custom_name(client, manager_token, buyer_token):
    pid = _create_product(client, buyer_token)
    r = client.post(
        "/requests",
        json={"product_id": pid, "custom_product_name": "Other", "quantity": 1},
        headers=auth_headers(manager_token),
    )
    assert r.status_code == 422


def test_request_rejects_neither_product_id_nor_custom_name(client, manager_token):
    r = client.post(
        "/requests",
        json={"quantity": 1},
        headers=auth_headers(manager_token),
    )
    assert r.status_code == 422


def test_request_rejects_zero_quantity(client, manager_token):
    r = client.post(
        "/requests",
        json={"custom_product_name": "Thing", "quantity": 0},
        headers=auth_headers(manager_token),
    )
    assert r.status_code == 422


def test_request_rejects_nonexistent_product(client, manager_token):
    r = client.post(
        "/requests",
        json={"product_id": 99999, "quantity": 1},
        headers=auth_headers(manager_token),
    )
    assert r.status_code == 404


def test_buyer_cannot_create_request(client, buyer_token):
    r = client.post(
        "/requests",
        json={"custom_product_name": "Thing", "quantity": 1},
        headers=auth_headers(buyer_token),
    )
    assert r.status_code == 403


def test_status_transition_pending_to_ordered(client, manager_token, buyer_token):
    r = client.post(
        "/requests",
        json={"custom_product_name": "X", "quantity": 1},
        headers=auth_headers(manager_token),
    )
    rid = r.json()["id"]
    r = client.patch(
        f"/requests/{rid}/status",
        json={"status": "ordered"},
        headers=auth_headers(buyer_token),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "ordered"


def test_status_transition_invalid_jump_rejected(client, manager_token, buyer_token):
    """Cannot go straight from pending to fulfilled, must go through ordered."""
    r = client.post(
        "/requests",
        json={"custom_product_name": "X", "quantity": 1},
        headers=auth_headers(manager_token),
    )
    rid = r.json()["id"]
    r = client.patch(
        f"/requests/{rid}/status",
        json={"status": "fulfilled"},
        headers=auth_headers(buyer_token),
    )
    assert r.status_code == 400


def test_cannot_transition_from_terminal_status(client, manager_token, buyer_token):
    r = client.post(
        "/requests",
        json={"custom_product_name": "X", "quantity": 1},
        headers=auth_headers(manager_token),
    )
    rid = r.json()["id"]
    client.patch(f"/requests/{rid}/status", json={"status": "ordered"}, headers=auth_headers(buyer_token))
    client.patch(f"/requests/{rid}/status", json={"status": "fulfilled"}, headers=auth_headers(buyer_token))
    r = client.patch(
        f"/requests/{rid}/status",
        json={"status": "ordered"},
        headers=auth_headers(buyer_token),
    )
    assert r.status_code == 400


def test_manager_only_sees_own_requests(client, manager_token):
    # Register a second manager
    client.post("/auth/register", json={
        "name": "Other Manager",
        "phone": "5559990000",
        "password": "password123",
        "role": "manager",
    })
    other_login = client.post("/auth/login", json={
        "phone": "5559990000",
        "password": "password123",
    }).json()
    other_token = other_login["access_token"]

    client.post("/requests", json={"custom_product_name": "Mine", "quantity": 1},
                headers=auth_headers(manager_token))
    client.post("/requests", json={"custom_product_name": "Theirs", "quantity": 1},
                headers=auth_headers(other_token))

    r = client.get("/requests", headers=auth_headers(manager_token))
    assert r.status_code == 200
    names = [req["custom_product_name"] for req in r.json()]
    assert "Mine" in names
    assert "Theirs" not in names


def test_unauthenticated_request_rejected(client):
    r = client.get("/requests")
    assert r.status_code == 401
