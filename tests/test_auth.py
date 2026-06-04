"""Tests for auth endpoints."""


def test_register_creates_user(client):
    r = client.post("/auth/register", json={
        "name": "Alice",
        "phone": "5551112222",
        "password": "supersecret",
    })
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Alice"
    assert body["plan"] == "free"
    assert "password" not in body  # never leak the password


def test_register_normalizes_phone(client):
    """Phone is stored in E.164 format regardless of how it was supplied."""
    r = client.post("/auth/register", json={
        "name": "Alice",
        "phone": "646-752-2092",
        "password": "supersecret",
    })
    assert r.status_code == 201
    assert r.json()["phone"] == "+16467522092"


def test_register_rejects_duplicate_phone(client):
    payload = {
        "name": "Alice",
        "phone": "5551113333",
        "password": "supersecret",
    }
    client.post("/auth/register", json=payload)
    r = client.post("/auth/register", json=payload)
    assert r.status_code == 409


def test_register_rejects_short_password(client):
    r = client.post("/auth/register", json={
        "name": "Alice",
        "phone": "5551114444",
        "password": "short",
    })
    assert r.status_code == 422


def test_login_returns_token(client):
    client.post("/auth/register", json={
        "name": "Bob",
        "phone": "5551115555",
        "password": "supersecret",
    })
    r = client.post("/auth/login", json={
        "phone": "5551115555",
        "password": "supersecret",
    })
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["user"]["plan"] == "free"


def test_login_rejects_wrong_password(client):
    client.post("/auth/register", json={
        "name": "Bob",
        "phone": "5551116666",
        "password": "supersecret",
    })
    r = client.post("/auth/login", json={
        "phone": "5551116666",
        "password": "wrongpass",
    })
    assert r.status_code == 401
