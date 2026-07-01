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
    assert r.json()["user"]["phone"] == "+16467522092"


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


def test_register_response_includes_business_name(client):
    """UserOut from registration includes business_name (null by default)."""
    r = register_user(client, "Alice", "5551117777", "supersecret")
    assert "business_name" in r
    assert r["business_name"] is None


def test_patch_me_updates_name_and_business_name(client):
    """PATCH /auth/me updates both fields and returns the updated user."""
    register_user(client, "Original", "5551118888", "password123")
    login_r = client.post("/auth/login", json={"phone": "5551118888", "password": "password123"})
    token = login_r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.patch("/auth/me", json={"name": "Updated", "business_name": "Acme Co"}, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Updated"
    assert body["business_name"] == "Acme Co"


def test_patch_me_clears_business_name(client):
    """Sending business_name: null explicitly clears the field."""
    register_user(client, "Alice", "5551119999", "password123")
    login_r = client.post("/auth/login", json={"phone": "5551119999", "password": "password123"})
    token = login_r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Set it first
    client.patch("/auth/me", json={"business_name": "Acme"}, headers=headers)
    # Now clear it
    r = client.patch("/auth/me", json={"business_name": None}, headers=headers)
    assert r.status_code == 200
    assert r.json()["business_name"] is None


def test_patch_me_requires_auth(client):
    r = client.patch("/auth/me", json={"name": "Hacker"})
    assert r.status_code == 401
