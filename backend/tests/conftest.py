"""Test fixtures: an isolated in-memory DB and a TestClient bound to it."""
from __future__ import annotations

import os
import tempfile

# Point the app at throwaway settings *before* importing anything that reads them.
os.environ["ATLAS_DATABASE_URL"] = "sqlite:///./test_atlas_ignored.db"
os.environ["ATLAS_AUTO_CREATE_TABLES"] = "false"
# Tests build their schema straight from the models on a throwaway in-memory
# engine; running Alembic here would migrate the file above instead.
os.environ["ATLAS_RUN_MIGRATIONS"] = "false"
# The background scheduler would run jobs against the real data dir mid-test.
os.environ["ATLAS_JOBS_ENABLED"] = "false"
# Keep trained model artifacts out of the real data dir during tests.
os.environ.setdefault("ATLAS_DATA_DIR", tempfile.mkdtemp(prefix="atlas_test_models_"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402,F401  (register tables)
from app.core.database import get_session  # noqa: E402
from app.core.scoping import set_current_user  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.services.auth_service import AuthService  # noqa: E402

#: Satisfies the password policy (8+ chars, letter, number, special).
TEST_PASSWORD = "Passw0rd!"
TEST_USERNAME = "tester"


def _fresh_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # one shared in-memory DB across connections
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    return engine, TestingSession()


def _bind(app, session):
    def _override():
        yield session

    app.dependency_overrides[get_session] = _override


@pytest.fixture()
def anon_client():
    """A client on an empty database: no account exists, no credentials sent.

    First-run and 401 behaviour needs a genuinely blank slate, which the signed-in
    ``client`` below deliberately isn't.
    """
    engine, session = _fresh_session()
    app = create_app()
    _bind(app, session)
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
        session.close()
        engine.dispose()


@pytest.fixture()
def db_session():
    """An isolated database with one account, already signed in.

    Data is account-scoped now, so a bare session can't read or write anything
    — ``app.core.scoping`` refuses to guess an owner. Binding the default
    account here keeps every test that talks to a service directly working the
    way it did when there was a single implicit vault.
    """
    engine, session = _fresh_session()
    user = AuthService(session).register(TEST_USERNAME, TEST_PASSWORD)
    set_current_user(session, user.id)
    session.info["test_user"] = user
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    """A TestClient signed in as the same account ``db_session`` is bound to."""
    app = create_app()
    _bind(app, db_session)
    with TestClient(app) as test_client:
        token = AuthService(db_session).start_session(db_session.info["test_user"])
        test_client.headers["Authorization"] = f"Bearer {token}"
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def other_client(db_session):
    """A second account on the same database — the other side of a leak test."""
    app = create_app()
    _bind(app, db_session)
    auth = AuthService(db_session)
    other = auth.register("intruder", TEST_PASSWORD)
    with TestClient(app) as test_client:
        test_client.headers["Authorization"] = f"Bearer {auth.start_session(other)}"
        yield test_client
    app.dependency_overrides.clear()
