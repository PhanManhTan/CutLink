import os

# The test database is disposable and MUST be separate from the application database.
os.environ.setdefault("JWT_SECRET", "test-secret-never-use-in-production-123456")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("ALLOWED_ORIGINS", '["http://testserver"]')
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://cutlink:cutlink-local-only@localhost:5432/cutlink_test",
)

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def migrate():
    if not engine.url.database.endswith("_test"):
        raise RuntimeError("Refusing to reset a database without the _test suffix")
    with engine.begin() as db:
        db.execute(text("DROP SCHEMA public CASCADE"))
        db.execute(text("CREATE SCHEMA public"))
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    command.upgrade(config, "head")
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def reset_database():
    with engine.begin() as db:
        db.execute(text("TRUNCATE users CASCADE"))


@pytest.fixture
def client():
    with TestClient(app, headers={"Origin": "http://testserver"}) as client:
        yield client


@pytest.fixture
def logged_in(client):
    response = client.post(
        "/api/auth/register",
        json={
            "email": "hello@example.com",
            "password": "a-long-password-123",
        },
    )
    assert response.status_code == 201
    return client


@pytest.fixture
def link(logged_in):
    response = logged_in.post(
        "/api/links",
        json={
            "name": "My portfolio",
            "target_url": "https://example.com/work?ref=short",
        },
    )
    assert response.status_code == 201
    return response.json()
