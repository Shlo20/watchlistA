"""Shared pytest fixtures. Uses an in-memory SQLite DB for fast, isolated tests."""
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


@pytest.fixture
def manager_token(client):
    client.post("/auth/register", json={
        "name": "Test Manager",
        "phone": "5551110001",
        "password": "password123",
        "role": "manager",
    })
    r = client.post("/auth/login", json={
        "phone": "5551110001",
        "password": "password123",
    })
    return r.json()["access_token"]


@pytest.fixture
def buyer_token(client):
    client.post("/auth/register", json={
        "name": "Test Buyer",
        "phone": "5552220001",
        "password": "password123",
        "role": "buyer",
    })
    r = client.post("/auth/login", json={
        "phone": "5552220001",
        "password": "password123",
    })
    return r.json()["access_token"]
