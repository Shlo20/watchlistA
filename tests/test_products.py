"""Tests for the product catalog endpoints."""


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def test_buyer_can_create_product(client, buyer_token):
    r = client.post(
        "/products",
        json={"name": "iPhone 15 Pro", "category": "phone", "brand": "Apple"},
        headers=auth_headers(buyer_token),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "iPhone 15 Pro"
    assert body["category"] == "phone"
    assert body["is_active"] is True


def test_manager_cannot_create_product(client, manager_token):
    r = client.post(
        "/products",
        json={"name": "Samsung Galaxy S24", "category": "phone"},
        headers=auth_headers(manager_token),
    )
    assert r.status_code == 403


def test_list_products_returns_created_catalog(client, buyer_token):
    products = [
        {"name": "iPhone 15", "category": "phone"},
        {"name": "iPad Air", "category": "tablet"},
        {"name": "OtterBox Case", "category": "case"},
    ]
    for p in products:
        client.post("/products", json=p, headers=auth_headers(buyer_token))

    r = client.get("/products", headers=auth_headers(buyer_token))
    assert r.status_code == 200
    names = [p["name"] for p in r.json()]
    assert "iPhone 15" in names
    assert "iPad Air" in names
    assert "OtterBox Case" in names


def test_search_filters_by_name(client, buyer_token):
    client.post("/products", json={"name": "iPhone 15", "category": "phone"},
                headers=auth_headers(buyer_token))
    client.post("/products", json={"name": "iPad Air", "category": "tablet"},
                headers=auth_headers(buyer_token))

    r = client.get("/products?search=iphone", headers=auth_headers(buyer_token))
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 1
    assert results[0]["name"] == "iPhone 15"


def test_filter_by_category(client, buyer_token):
    client.post("/products", json={"name": "iPhone 15", "category": "phone"},
                headers=auth_headers(buyer_token))
    client.post("/products", json={"name": "OtterBox Case", "category": "case"},
                headers=auth_headers(buyer_token))

    r = client.get("/products?category=phone", headers=auth_headers(buyer_token))
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 1
    assert results[0]["category"] == "phone"


def test_get_nonexistent_product_returns_404(client, buyer_token):
    r = client.get("/products/99999", headers=auth_headers(buyer_token))
    assert r.status_code == 404
