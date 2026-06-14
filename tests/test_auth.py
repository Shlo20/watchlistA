"""Tests for auth endpoints."""
from tests.conftest import register_user


def test_register_creates_user(client):
    r = register_user(client, "Alice", "5551112222", "supersecret")
    assert r["name"] == "Alice"
    assert r["plan"] == "free"
    assert "password" not in r  # never leak the password


def test_register_normalizes_phone(client):
    """Phone is stored in E.164 format regardless of how it was supplied."""
    client.post("/auth/request-code", json={"phone": "646-752-2092"})
    r = client.post("/auth/register", json={
        "name": "Alice",
        "phone": "646-752-2092",
        "password": "supersecret",
        "code": "000000",
    })
    assert r.status_code == 201
    assert r.json()["phone"] == "+16467522092"


def test_register_rejects_duplicate_phone(client):
    register_user(client, "Alice", "5551113333", "supersecret")
    # Need a fresh code for the second attempt (first was consumed)
    client.post("/auth/request-code", json={"phone": "5551113333"})
    r = client.post("/auth/register", json={
        "name": "Alice",
        "phone": "5551113333",
        "password": "supersecret",
        "code": "000000",
    })
    assert r.status_code == 409


def test_register_rejects_short_password(client):
    client.post("/auth/request-code", json={"phone": "5551114444"})
    r = client.post("/auth/register", json={
        "name": "Alice",
        "phone": "5551114444",
        "password": "short",
        "code": "000000",
    })
    assert r.status_code == 422


def test_login_returns_token(client):
    register_user(client, "Bob", "5551115555", "supersecret")
    r = client.post("/auth/login", json={"phone": "5551115555", "password": "supersecret"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["user"]["plan"] == "free"


def test_login_rejects_wrong_password(client):
    register_user(client, "Bob", "5551116666", "supersecret")
    r = client.post("/auth/login", json={"phone": "5551116666", "password": "wrongpass"})
    assert r.status_code == 401
