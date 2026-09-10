"""Auth flow tests against an in-memory SQLite database.

The FastAPI dependency `get_session` is overridden so no network or real
Postgres is involved; the whole signup -> login -> me -> logout loop runs
in milliseconds. SQLite and Postgres behave the same for this schema.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_session
from app.main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # one shared in-memory DB across connections
    )
    Base.metadata.create_all(engine)

    def override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override
    # No `with` block: that would run the app lifespan, which does
    # create_all against the real Postgres. The fixture already made tables.
    yield TestClient(app)
    app.dependency_overrides.clear()


CREDS = {"email": "terp@umd.edu", "password": "correct-horse-battery"}


def test_signup_login_me_logout_roundtrip(client):
    assert client.post("/api/auth/signup", json=CREDS).status_code == 201
    assert client.get("/api/auth/me").json() == {"email": "terp@umd.edu"}

    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").status_code == 401

    assert client.post("/api/auth/login", json=CREDS).status_code == 200
    assert client.get("/api/auth/me").json() == {"email": "terp@umd.edu"}


def test_duplicate_email_rejected(client):
    client.post("/api/auth/signup", json=CREDS)
    assert client.post("/api/auth/signup", json=CREDS).status_code == 409


def test_wrong_password_and_unknown_email_same_error(client):
    client.post("/api/auth/signup", json=CREDS)
    wrong = client.post("/api/auth/login", json={**CREDS, "password": "wrong-password"})
    unknown = client.post("/api/auth/login", json={"email": "ghost@umd.edu", "password": "whatever12"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_email_case_insensitive(client):
    client.post("/api/auth/signup", json=CREDS)
    upper = client.post("/api/auth/login", json={**CREDS, "email": "TERP@UMD.EDU"})
    assert upper.status_code == 200


def test_short_password_rejected(client):
    resp = client.post("/api/auth/signup", json={"email": "a@b.edu", "password": "short"})
    assert resp.status_code == 422


def test_me_requires_cookie(client):
    assert client.get("/api/auth/me").status_code == 401
