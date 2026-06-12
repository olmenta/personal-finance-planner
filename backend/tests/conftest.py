"""Test fixtures — Postgres (Neon test branch) via TEST_DATABASE_URL.

Schema is created once per session; each test runs inside a transaction that
is rolled back, so tests never leak state into the branch.
"""

import os

# Before app import: app.main runs configure_sentry() at import time, and a
# developer's .env DSN would make test-triggered warnings send real events.
os.environ["SENTRY_DSN"] = ""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.main import app
from app.models import Base
from app.seed import seed

TEST_URL = os.environ.get("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(not TEST_URL, reason="TEST_DATABASE_URL not set")


@pytest.fixture(autouse=True)
def no_live_llm(monkeypatch):
    """Tests never call Anthropic. Settings loads backend/.env, so a real
    ANTHROPIC_API_KEY there would leak in and make import tests do live LLM
    calls (slow, flaky, costs tokens). Env vars beat env_file values."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def engine():
    if not TEST_URL:
        pytest.skip("TEST_DATABASE_URL not set")
    eng = create_engine(TEST_URL, pool_pre_ping=True)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def user(db):
    return seed(db)


@pytest.fixture
def client(db, user):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def category_ids(client):
    """name -> id over the seeded tree."""
    groups = client.get("/categories").json()
    return {c["name"]: c["id"] for g in groups for c in g["categories"]}
