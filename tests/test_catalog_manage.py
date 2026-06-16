"""Tests for catalog dedupe, soft-delete, restore, and list-all."""


def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── Dedupe on create ───────────────────────────────────────────────────────

def test_create_duplicate_name_returns_existing(client, buyer_token):
    h = auth(buyer_token)
    r1 = client.post("/products", json={"name": "AirPods"}, headers=h)
    assert r1.status_code == 201
    pid = r1.json()["id"]

    r2 = client.post("/products", json={"name": "AirPods"}, headers=h)
    assert r2.status_code == 200
    assert r2.json()["id"] == pid

    # Exactly one row with that name in the catalog
    all_r = client.get("/products/all", headers=h)
    assert sum(1 for p in all_r.json() if p["name"] == "AirPods") == 1


def test_create_dedup_case_insensitive(client, buyer_token):
    h = auth(buyer_token)
    r1 = client.post("/products", json={"name": "iPhone 15"}, headers=h)
    assert r1.status_code == 201
    pid = r1.json()["id"]

    r2 = client.post("/products", json={"name": "iphone 15"}, headers=h)
    assert r2.status_code == 200
    assert r2.json()["id"] == pid


def test_create_dedup_whitespace_trimmed(client, buyer_token):
    h = auth(buyer_token)
    r1 = client.post("/products", json={"name": "Galaxy Tab"}, headers=h)
    assert r1.status_code == 201
    pid = r1.json()["id"]

    r2 = client.post("/products", json={"name": "  Galaxy Tab  "}, headers=h)
    assert r2.status_code == 200
    assert r2.json()["id"] == pid


def test_create_reactivates_soft_deleted(client, buyer_token):
    h = auth(buyer_token)
    r1 = client.post("/products", json={"name": "Old Cable"}, headers=h)
    assert r1.status_code == 201
    pid = r1.json()["id"]

    # Soft-delete it
    assert client.delete(f"/products/{pid}", headers=h).status_code == 204

    # Not in search or /all
    s1 = client.get("/products?search=Old+Cable", headers=h)
    assert all(p["id"] != pid for p in s1.json())
    all1 = client.get("/products/all", headers=h)
    assert all(p["id"] != pid for p in all1.json())

    # Re-create same name → reactivates, same row
    r2 = client.post("/products", json={"name": "Old Cable"}, headers=h)
    assert r2.status_code == 200
    assert r2.json()["id"] == pid
    assert r2.json()["is_active"] is True

    # Now visible again
    s2 = client.get("/products?search=Old+Cable", headers=h)
    assert any(p["id"] == pid for p in s2.json())


# ── Soft-delete ────────────────────────────────────────────────────────────

def test_soft_delete_sets_inactive_and_hides_from_search(client, buyer_token):
    h = auth(buyer_token)
    r = client.post("/products", json={"name": "Screen Protector Pro"}, headers=h)
    pid = r.json()["id"]

    s1 = client.get("/products?search=Screen+Protector", headers=h)
    assert any(p["id"] == pid for p in s1.json())

    del_r = client.delete(f"/products/{pid}", headers=h)
    assert del_r.status_code == 204

    # No longer in search or list-all
    s2 = client.get("/products?search=Screen+Protector", headers=h)
    assert all(p["id"] != pid for p in s2.json())
    all_r = client.get("/products/all", headers=h)
    assert all(p["id"] != pid for p in all_r.json())


def test_soft_delete_nonexistent_returns_404(client, buyer_token):
    r = client.delete("/products/9999", headers=auth(buyer_token))
    assert r.status_code == 404


def test_soft_delete_unauthenticated_returns_401(client, buyer_token):
    h = auth(buyer_token)
    r = client.post("/products", json={"name": "Unauthed Delete Test"}, headers=h)
    pid = r.json()["id"]
    assert client.delete(f"/products/{pid}").status_code == 401


# ── Restore ────────────────────────────────────────────────────────────────

def test_restore_brings_product_back(client, buyer_token):
    h = auth(buyer_token)
    r = client.post("/products", json={"name": "Restored Item"}, headers=h)
    pid = r.json()["id"]

    client.delete(f"/products/{pid}", headers=h)

    restore_r = client.post(f"/products/{pid}/restore", headers=h)
    assert restore_r.status_code == 200
    assert restore_r.json()["id"] == pid
    assert restore_r.json()["is_active"] is True

    # Visible in search again
    s = client.get("/products?search=Restored", headers=h)
    assert any(p["id"] == pid for p in s.json())


def test_restore_nonexistent_returns_404(client, buyer_token):
    r = client.post("/products/9999/restore", headers=auth(buyer_token))
    assert r.status_code == 404


# ── List all ──────────────────────────────────────────────────────────────

def test_list_all_returns_active_only(client, buyer_token):
    h = auth(buyer_token)
    r1 = client.post("/products", json={"name": "Active Product"}, headers=h)
    r2 = client.post("/products", json={"name": "Inactive Product"}, headers=h)
    pid_active = r1.json()["id"]
    pid_inactive = r2.json()["id"]

    client.delete(f"/products/{pid_inactive}", headers=h)

    all_r = client.get("/products/all", headers=h)
    assert all_r.status_code == 200
    ids = [p["id"] for p in all_r.json()]
    assert pid_active in ids
    assert pid_inactive not in ids


def test_list_all_unauthenticated_returns_401(client):
    assert client.get("/products/all").status_code == 401
