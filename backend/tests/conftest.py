"""Test fixtures: an isolated in-memory DB and a TestClient bound to it."""
from __future__ import annotations

import os
import tempfile

# Point the app at throwaway settings *before* importing anything that reads them.
os.environ["ATLAS_DATABASE_URL"] = "sqlite:///./test_atlas_ignored.db"
os.environ["ATLAS_AUTO_CREATE_TABLES"] = "false"
# Keep trained model artifacts out of the real data dir during tests.
os.environ.setdefault("ATLAS_DATA_DIR", tempfile.mkdtemp(prefix="atlas_test_models_"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.models  # noqa: E402,F401  (register tables)
from app.core.database import get_session  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.base import Base  # noqa: E402


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,  # one shared in-memory DB across connections
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    app = create_app()

    def _override():
        yield db_session

    app.dependency_overrides[get_session] = _override
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
