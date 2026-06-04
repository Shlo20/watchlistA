"""Tests for the /contacts endpoints."""


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _create(client, token, nickname="Alice", phone="6467522092"):
    return client.post(
        "/contacts",
        json={"nickname": nickname, "phone": phone},
        headers=auth_headers(token),
    )


# ── create ────────────────────────────────────────────────────────────────────

def test_create_contact(client, manager_token):
    r = _create(client, manager_token)
    assert r.status_code == 201
    body = r.json()
    assert body["nickname"] == "Alice"
    assert body["phone"] == "+16467522092"
    assert body["owner_user_id"] is not None
    assert body["linked_user_id"] is None
    assert "id" in body


def test_create_contact_normalizes_phone(client, manager_token):
    """Hyphenated and parenthesised formats all resolve to E.164."""
    r = _create(client, manager_token, phone="646-752-2092")
    assert r.status_code == 201
    assert r.json()["phone"] == "+16467522092"


def test_create_contact_duplicate_phone_rejected(client, manager_token):
    """Same (owner, phone) pair → 409."""
    _create(client, manager_token, nickname="First")
    r = _create(client, manager_token, nickname="Second")
    assert r.status_code == 409


def test_create_contact_invalid_phone_rejected(client, manager_token):
    r = client.post(
        "/contacts",
        json={"nickname": "Bad", "phone": "not-a-phone"},
        headers=auth_headers(manager_token),
    )
    assert r.status_code == 422


def test_different_owners_may_save_same_phone(client, manager_token, buyer_token):
    """The unique constraint is (owner, phone), not just phone."""
    r1 = _create(client, manager_token)
    r2 = _create(client, buyer_token)  # same phone, different owner
    assert r1.status_code == 201
    assert r2.status_code == 201


# ── list ──────────────────────────────────────────────────────────────────────

def test_list_contacts_returns_only_own(client, manager_token, buyer_token):
    """Ownership isolation: each user's list is scoped to themselves."""
    _create(client, manager_token, nickname="Manager Contact", phone="6467522092")
    _create(client, buyer_token, nickname="Buyer Contact", phone="9175550001")

    r = client.get("/contacts", headers=auth_headers(manager_token))
    assert r.status_code == 200
    names = [c["nickname"] for c in r.json()]
    assert "Manager Contact" in names
    assert "Buyer Contact" not in names


def test_list_contacts_ordered_by_nickname(client, manager_token):
    _create(client, manager_token, nickname="Zara", phone="6467522092")
    _create(client, manager_token, nickname="Aaron", phone="9175550001")
    r = client.get("/contacts", headers=auth_headers(manager_token))
    assert r.status_code == 200
    names = [c["nickname"] for c in r.json()]
    assert names == sorted(names)


# ── get ───────────────────────────────────────────────────────────────────────

def test_get_contact(client, manager_token):
    cid = _create(client, manager_token).json()["id"]
    r = client.get(f"/contacts/{cid}", headers=auth_headers(manager_token))
    assert r.status_code == 200
    assert r.json()["id"] == cid


def test_get_contact_not_owned_returns_404(client, manager_token, buyer_token):
    cid = _create(client, manager_token).json()["id"]
    r = client.get(f"/contacts/{cid}", headers=auth_headers(buyer_token))
    assert r.status_code == 404


# ── patch ─────────────────────────────────────────────────────────────────────

def test_patch_contact_nickname(client, manager_token):
    cid = _create(client, manager_token).json()["id"]
    r = client.patch(
        f"/contacts/{cid}",
        json={"nickname": "Alice Updated"},
        headers=auth_headers(manager_token),
    )
    assert r.status_code == 200
    assert r.json()["nickname"] == "Alice Updated"
    assert r.json()["phone"] == "+16467522092"  # phone unchanged


def test_patch_contact_phone_normalizes(client, manager_token):
    cid = _create(client, manager_token).json()["id"]
    r = client.patch(
        f"/contacts/{cid}",
        json={"phone": "718-555-0001"},
        headers=auth_headers(manager_token),
    )
    assert r.status_code == 200
    assert r.json()["phone"] == "+17185550001"


def test_patch_contact_invalid_phone_returns_422(client, manager_token):
    cid = _create(client, manager_token).json()["id"]
    r = client.patch(
        f"/contacts/{cid}",
        json={"phone": "bad-phone"},
        headers=auth_headers(manager_token),
    )
    assert r.status_code == 422


def test_patch_contact_not_owned_returns_404(client, manager_token, buyer_token):
    cid = _create(client, manager_token).json()["id"]
    r = client.patch(
        f"/contacts/{cid}",
        json={"nickname": "Hacked"},
        headers=auth_headers(buyer_token),
    )
    assert r.status_code == 404


# ── delete ────────────────────────────────────────────────────────────────────

def test_delete_contact(client, manager_token):
    cid = _create(client, manager_token).json()["id"]
    r = client.delete(f"/contacts/{cid}", headers=auth_headers(manager_token))
    assert r.status_code == 204
    assert client.get(f"/contacts/{cid}", headers=auth_headers(manager_token)).status_code == 404


def test_delete_contact_not_owned_returns_404(client, manager_token, buyer_token):
    cid = _create(client, manager_token).json()["id"]
    r = client.delete(f"/contacts/{cid}", headers=auth_headers(buyer_token))
    assert r.status_code == 404
    # Original contact still exists for its owner
    assert client.get(f"/contacts/{cid}", headers=auth_headers(manager_token)).status_code == 200
