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


# --- Search edge case tests ---

def _make_iphone(client, buyer_token, name="iPhone 15"):
    client.post("/products", json={"name": name, "category": "phone"},
                headers=auth_headers(buyer_token))


def test_search_ignores_spaces_in_query(client, buyer_token):
    """'iphone15' (no space) matches product named 'iPhone 15'."""
    _make_iphone(client, buyer_token)
    r = client.get("/products?search=iphone15", headers=auth_headers(buyer_token))
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_search_ignores_case_uppercase(client, buyer_token):
    """All-caps query matches case-insensitively."""
    _make_iphone(client, buyer_token)
    r = client.get("/products?search=IPHONE", headers=auth_headers(buyer_token))
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_search_ignores_case_mixed(client, buyer_token):
    """Mixed-case query matches case-insensitively."""
    _make_iphone(client, buyer_token)
    r = client.get("/products?search=IpHoNe", headers=auth_headers(buyer_token))
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_search_handles_extra_whitespace(client, buyer_token):
    """Leading, trailing, and internal extra spaces are all stripped/collapsed."""
    _make_iphone(client, buyer_token)
    r = client.get("/products?search=  iphone  15  ", headers=auth_headers(buyer_token))
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_search_partial_word_match(client, buyer_token):
    """A prefix substring still matches."""
    _make_iphone(client, buyer_token)
    r = client.get("/products?search=iph", headers=auth_headers(buyer_token))
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_search_alphanumeric_match(client, buyer_token):
    """Numbers and letters run together match across the space in the product name."""
    _make_iphone(client, buyer_token, name="iPhone 15 Pro")
    r = client.get("/products?search=15pro", headers=auth_headers(buyer_token))
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_search_no_match_returns_empty(client, buyer_token):
    """Non-matching query returns 200 with an empty list, not a 404."""
    _make_iphone(client, buyer_token)
    r = client.get("/products?search=samsung", headers=auth_headers(buyer_token))
    assert r.status_code == 200
    assert r.json() == []


def test_search_excludes_inactive_products(client, db_session, buyer_token):
    """Inactive products are hidden from search results."""
    from app.models.product import Product

    _make_iphone(client, buyer_token)

    session, _ = db_session
    product = session.query(Product).filter(Product.name == "iPhone 15").first()
    product.is_active = False
    session.commit()

    r = client.get("/products?search=iphone", headers=auth_headers(buyer_token))
    assert r.status_code == 200
    assert r.json() == []


def test_search_combined_with_category_filter(client, buyer_token):
    """Search term and category filter are ANDed together."""
    client.post("/products", json={"name": "iPhone 15 Case", "category": "case"},
                headers=auth_headers(buyer_token))
    client.post("/products", json={"name": "iPhone 15 Pro", "category": "phone"},
                headers=auth_headers(buyer_token))

    r = client.get("/products?search=iphone&category=case", headers=auth_headers(buyer_token))
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 1
    assert results[0]["name"] == "iPhone 15 Case"
