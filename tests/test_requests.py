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
        json={"product_id": pid, "quantity": 5},
        headers=auth_headers(manager_token),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert body["quantity"] == 5


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


def test_any_authenticated_user_can_create_request(client, buyer_token):
    """Any authenticated user can create a restock request — no role required."""
    r = client.post(
        "/requests",
        json={"custom_product_name": "Thing", "quantity": 1},
        headers=auth_headers(buyer_token),
    )
    assert r.status_code == 201


def test_status_transition_pending_to_done(client, manager_token, buyer_token):
    r = client.post(
        "/requests",
        json={"custom_product_name": "X", "quantity": 1},
        headers=auth_headers(manager_token),
    )
    rid = r.json()["id"]
    r = client.patch(
        f"/requests/{rid}/status",
        json={"status": "done"},
        headers=auth_headers(buyer_token),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "done"


def test_cannot_transition_from_terminal_status(client, manager_token, buyer_token):
    r = client.post(
        "/requests",
        json={"custom_product_name": "X", "quantity": 1},
        headers=auth_headers(manager_token),
    )
    rid = r.json()["id"]
    client.patch(f"/requests/{rid}/status", json={"status": "done"}, headers=auth_headers(buyer_token))
    r = client.patch(
        f"/requests/{rid}/status",
        json={"status": "done"},
        headers=auth_headers(buyer_token),
    )
    assert r.status_code == 400


def test_user_sees_only_own_requests(client, manager_token):
    """Ownership-based isolation: each user's list contains only their own requests."""
    from tests.conftest import register_user
    register_user(client, "Other User", "5559990000")
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


def test_any_authenticated_user_can_bulk_clear_pending_requests(client, manager_token, buyer_token):
    for name in ("Item A", "Item B", "Item C"):
        client.post(
            "/requests",
            json={"custom_product_name": name, "quantity": 1},
            headers=auth_headers(manager_token),
        )

    r = client.post("/requests/clear-all", headers=auth_headers(buyer_token))
    assert r.status_code == 200
    body = r.json()
    assert body["cleared_count"] == 3
    assert len(body["request_ids"]) == 3

    # Verify using the creator's token (owners see their own requests)
    listing = client.get("/requests", headers=auth_headers(manager_token)).json()
    assert all(req["status"] == "done" for req in listing)


def test_manager_can_now_mark_request_done(client, manager_token):
    r = client.post(
        "/requests",
        json={"custom_product_name": "Widget", "quantity": 1},
        headers=auth_headers(manager_token),
    )
    rid = r.json()["id"]
    r = client.patch(
        f"/requests/{rid}/status",
        json={"status": "done"},
        headers=auth_headers(manager_token),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "done"


def test_buyer_can_still_mark_request_done(client, manager_token, buyer_token):
    r = client.post(
        "/requests",
        json={"custom_product_name": "Widget", "quantity": 1},
        headers=auth_headers(manager_token),
    )
    rid = r.json()["id"]
    r = client.patch(
        f"/requests/{rid}/status",
        json={"status": "done"},
        headers=auth_headers(buyer_token),
    )
    assert r.status_code == 200
    assert r.json()["status"] == "done"


def test_manager_can_clear_all(client, manager_token):
    for name in ("A", "B", "C"):
        client.post(
            "/requests",
            json={"custom_product_name": name, "quantity": 1},
            headers=auth_headers(manager_token),
        )
    r = client.post("/requests/clear-all", headers=auth_headers(manager_token))
    assert r.status_code == 200
    assert r.json()["cleared_count"] == 3


def test_mark_done_endpoint_marks_specified_requests(client, manager_token, buyer_token):
    ids = []
    for name in ("X", "Y", "Z"):
        r = client.post(
            "/requests",
            json={"custom_product_name": name, "quantity": 1},
            headers=auth_headers(manager_token),
        )
        ids.append(r.json()["id"])

    r = client.post(
        "/requests/mark-done",
        json={"request_ids": ids[:2]},
        headers=auth_headers(buyer_token),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["marked_count"] == 2
    assert set(body["request_ids"]) == set(ids[:2])

    # Use the creator's token — list is ownership-scoped
    listing = {req["id"]: req["status"] for req in
               client.get("/requests", headers=auth_headers(manager_token)).json()}
    assert listing[ids[0]] == "done"
    assert listing[ids[1]] == "done"
    assert listing[ids[2]] == "pending"


def test_mark_done_silently_skips_missing_ids(client, manager_token, buyer_token):
    r = client.post(
        "/requests",
        json={"custom_product_name": "Real Item", "quantity": 1},
        headers=auth_headers(manager_token),
    )
    real_id = r.json()["id"]

    r = client.post(
        "/requests/mark-done",
        json={"request_ids": [real_id, 99999]},
        headers=auth_headers(buyer_token),
    )
    assert r.status_code == 200
    assert r.json()["marked_count"] == 1


def test_mark_done_skips_already_done_requests(client, manager_token, buyer_token):
    r = client.post(
        "/requests",
        json={"custom_product_name": "Already Done", "quantity": 1},
        headers=auth_headers(manager_token),
    )
    rid = r.json()["id"]
    client.patch(f"/requests/{rid}/status", json={"status": "done"},
                 headers=auth_headers(buyer_token))

    r = client.post(
        "/requests/mark-done",
        json={"request_ids": [rid]},
        headers=auth_headers(buyer_token),
    )
    assert r.status_code == 200
    assert r.json()["marked_count"] == 0


def test_mark_done_requires_authentication(client):
    r = client.post("/requests/mark-done", json={"request_ids": [1]})
    assert r.status_code == 401


def test_mark_done_works_for_multiple_users(client, manager_token, buyer_token):
    r1 = client.post("/requests", json={"custom_product_name": "For Buyer", "quantity": 1},
                     headers=auth_headers(manager_token))
    r2 = client.post("/requests", json={"custom_product_name": "For Manager", "quantity": 1},
                     headers=auth_headers(manager_token))
    id1 = r1.json()["id"]
    id2 = r2.json()["id"]

    rb = client.post("/requests/mark-done", json={"request_ids": [id1]},
                     headers=auth_headers(buyer_token))
    assert rb.status_code == 200
    assert rb.json()["marked_count"] == 1

    rm = client.post("/requests/mark-done", json={"request_ids": [id2]},
                     headers=auth_headers(manager_token))
    assert rm.status_code == 200
    assert rm.json()["marked_count"] == 1


def test_send_digest_returns_count_of_pending_items(client, manager_token, buyer_token):
    for name in ("Item A", "Item B", "Item C"):
        client.post("/requests", json={"custom_product_name": name, "quantity": 1},
                    headers=auth_headers(manager_token))

    r = client.post("/requests/send-digest", headers=auth_headers(buyer_token))
    assert r.status_code == 200
    assert r.json()["items_in_digest"] == 3


def test_send_digest_with_no_pending_returns_zero(client, buyer_token):
    r = client.post("/requests/send-digest", headers=auth_headers(buyer_token))
    assert r.status_code == 200
    assert r.json()["items_in_digest"] == 0


def test_create_request_no_longer_triggers_per_item_notification(client, manager_token):
    from unittest.mock import MagicMock, patch
    from app.services import notifications

    mock_fn = MagicMock()
    with patch.object(notifications, "notify_buyers_new_request", mock_fn):
        r = client.post("/requests", json={"custom_product_name": "Thing", "quantity": 1},
                        headers=auth_headers(manager_token))
        assert r.status_code == 201
    mock_fn.assert_not_called()


def test_archive_stale_marks_old_pending_as_done(client, db_session, manager_token, buyer_token):
    from datetime import datetime, timedelta, timezone
    from app.models.request import Request

    r1 = client.post("/requests", json={"custom_product_name": "Old Item", "quantity": 1},
                     headers=auth_headers(manager_token))
    r2 = client.post("/requests", json={"custom_product_name": "New Item", "quantity": 1},
                     headers=auth_headers(manager_token))
    old_id = r1.json()["id"]
    new_id = r2.json()["id"]

    # Backdate the first request to 49 hours ago so it falls past the 48-hour cutoff
    session, _ = db_session
    req = session.query(Request).filter(Request.id == old_id).first()
    req.created_at = datetime.now(timezone.utc) - timedelta(hours=49)
    session.commit()

    r = client.post("/requests/archive-stale", headers=auth_headers(buyer_token))
    assert r.status_code == 200
    assert r.json()["archived_count"] == 1

    # Use the creator's token — list is ownership-scoped
    listing = {req["id"]: req["status"] for req in
               client.get("/requests", headers=auth_headers(manager_token)).json()}
    assert listing[old_id] == "done"
    assert listing[new_id] == "pending"


def test_archive_stale_accessible_to_any_authenticated_user(client, manager_token):
    """archive-stale is no longer role-gated — any authenticated user can call it."""
    r = client.post("/requests/archive-stale", headers=auth_headers(manager_token))
    assert r.status_code == 200


def test_unauthenticated_request_rejected(client):
    r = client.get("/requests")
    assert r.status_code == 401


def test_send_digest_does_not_call_brevo_when_sms_disabled(client, manager_token, buyer_token):
    """SMS_ENABLED=false (set in conftest) must never make an outbound HTTP call to Brevo."""
    from unittest.mock import patch
    import httpx

    # Register a user with a known phone + carrier so _build_sms_email returns an address
    client.post("/auth/register", json={
        "name": "SMS User",
        "phone": "6467522092",
        "password": "password123",
        "carrier": "simple",
    })

    client.post("/requests", json={"custom_product_name": "Widget", "quantity": 1},
                headers=auth_headers(manager_token))

    with patch.object(httpx, "post") as mock_post:
        r = client.post("/requests/send-digest", headers=auth_headers(buyer_token))
        assert r.status_code == 200
        assert r.json()["items_in_digest"] == 1
        mock_post.assert_not_called()
