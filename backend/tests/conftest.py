"""Tests run against the configured MySQL database inside one outer transaction that is
rolled back at the end, so no test data is left behind. Requires migrations + seed."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

os.environ.setdefault("DECISION_APPLY_MINUTES", "0")  # no background job inside the tests
os.environ.setdefault("MAINTENANCE_MINUTES", "0")

from app.core.database import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services import background  # noqa: E402


@pytest.fixture()
def db_session():
    conn = engine.connect()
    trans = conn.begin()
    session = Session(bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        trans.rollback()
        conn.close()


@pytest.fixture()
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    background.inline_session = lambda: db_session  # background work (exports, dashboard) done in the test's session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    background.inline_session = None


@pytest.fixture()
def admin(client):
    r = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@123"})
    assert r.status_code == 200, r.text
    client.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return client
