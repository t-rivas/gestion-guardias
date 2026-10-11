import re
import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.base import Base
from app.db.database import get_db
from app.main import app
from app.models import Account, PlanningState
from app.security import password_hash


@pytest.fixture
def factory():
    database_url = os.getenv("TEST_DATABASE_URL")
    if database_url:
        if not database_url.endswith("/hydroid_checks"):
            raise RuntimeError(
                "PostgreSQL test URL must target the disposable hydroid_checks database"
            )
        engine = create_engine(database_url)
    else:
        engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
        )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False)
    with factory() as db:
        db.add(PlanningState(id=1, revision=0))
        db.commit()
    yield factory
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db(factory):
    with factory() as session:
        yield session


@pytest.fixture
def client(factory):
    previous = app.state.session_factory
    app.state.session_factory = factory

    def dependency():
        with factory() as db:
            try:
                yield db
            except Exception:
                db.rollback()
                raise

    app.dependency_overrides[get_db] = dependency
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    app.state.session_factory = previous


def token(response):
    return re.search(r'name="csrf_token" value="([^"]+)"', response.text).group(1)


def revision(response):
    return int(re.search(r'name="revision" value="([^"]+)"', response.text).group(1))


@pytest.fixture(params=["password", "neon"])
def signed_client(client, request):
    if request.param == "neon":
        neon = request.getfixturevalue("neon")
        response = client.get(
            "/auth/callback?token=valid-token", follow_redirects=False
        )
        assert response.status_code == 303
        return neon["client"]

    page = client.get("/setup")
    response = client.post(
        "/setup",
        data={
            "csrf_token": token(page),
            "username": "admin",
            "password": "test-password-123",
            "confirm_password": "test-password-123",
        },
    )
    assert response.status_code == 200
    return client


@pytest.fixture
def neon(client, monkeypatch):
    from tests.neon_provider import configure_neon

    return configure_neon(client, monkeypatch)
