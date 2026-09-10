"""Shared test fixtures.

`client` gives every test a FastAPI TestClient wired to a fresh in-memory
SQLite database — no network, no Postgres, each test fully isolated.
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
    test_client = TestClient(app)
    test_client.engine = engine  # so tests can seed data directly
    yield test_client
    app.dependency_overrides.clear()
