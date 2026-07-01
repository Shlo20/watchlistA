"""Shared pytest fixtures. Uses an in-memory SQLite DB for fast, isolated tests."""
import os
os.environ["SCHEDULER_ENABLED"] = "false"
os.environ["SMS_ENABLED"] = "false"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models import *  # noqa: F401,F403  -- ensure all models register on Base


@pytest.fixture(autouse=True)
def disable_notifications(monkeypatch):
    """Stub out background notifications so tests don't hit the real DB or network."""
    from app.services import notifications
    monkeypatch.setattr(notifications, "notify_buyers_new_request", lambda *a, **kw: None)
    monkeypatch.setattr(notifications, "notify_requester_status_change", lambda *a, **kw: None)


@pytest.fixture
def db_session():
    """Fresh in-memory DB for every test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session, TestingSession
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    """FastAPI test client wired to the test DB."""
    _, TestingSession = db_session

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def register_user(client, name, phone, password="password123", carrier=None):
    """Two-step registration helper: POST /auth/request-code then /auth/register with code='000000'."""
    client.post("/auth/request-code", json={"phone": phone})
    payload = {"name": name, "phone": phone, "password": password, "code": "000000"}
    if carrier is not None:
        payload["carrier"] = carrier
    r = client.post("/auth/register", json=payload)
    assert r.status_code == 201, f"register_user failed: {r.status_code} {r.json()}"
    body = r.json()
    assert body.get("access_token"), "register must return a usable token"
    return body["user"]


@pytest.fixture
def manager_token(client):
    register_user(client, "Test Manager", "5551110001")
    r = client.post("/auth/login", json={"phone": "5551110001", "password": "password123"})
    return r.json()["access_token"]


@pytest.fixture
def buyer_token(client):
    register_user(client, "Test Buyer", "5552220001")
    r = client.post("/auth/login", json={"phone": "5552220001", "password": "password123"})
    return r.json()["access_token"]
