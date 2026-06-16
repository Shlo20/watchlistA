"""Tests for name-only product creation and catalog search integration."""


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_create_product_name_only(client, buyer_token):
    """POST /products with only a name should succeed, defaulting category to 'other'."""
    r = client.post("/products", json={"name": "Wireless Charger"}, headers=auth(buyer_token))
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Wireless Charger"
    assert body["category"] == "other"
    assert body["is_active"] is True
    assert body["is_low"] is False


def test_create_product_name_only_appears_in_search(client, buyer_token):
    """A name-only product should appear in GET /products?search= results."""
    client.post("/products", json={"name": "Tempered Glass 2024"}, headers=auth(buyer_token))
    r = client.get("/products?search=tempered", headers=auth(buyer_token))
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 1
    assert results[0]["name"] == "Tempered Glass 2024"
    assert results[0]["category"] == "other"


def test_create_product_with_explicit_category_still_works(client, buyer_token):
    """Supplying category explicitly still works and overrides the default."""
    r = client.post(
        "/products",
        json={"name": "Galaxy S24", "category": "phone"},
        headers=auth(buyer_token),
    )
    assert r.status_code == 201
    assert r.json()["category"] == "phone"


def test_create_product_name_only_serializes_in_list(client, buyer_token):
    """Name-only (other-category) product serializes without error in GET /products."""
    client.post("/products", json={"name": "Generic Cable"}, headers=auth(buyer_token))
    r = client.get("/products", headers=auth(buyer_token))
    assert r.status_code == 200
    names = [p["name"] for p in r.json()]
    assert "Generic Cable" in names


def test_create_product_requires_name(client, buyer_token):
    """Empty-name product should be rejected with 422."""
    r = client.post("/products", json={"name": ""}, headers=auth(buyer_token))
    assert r.status_code == 422


def test_create_product_unauthenticated_returns_401(client):
    """Unauthenticated requests must be rejected."""
    r = client.post("/products", json={"name": "Stealth Item"})
    assert r.status_code == 401
