"""Test fixtures: a real Postgres test database migrated with Alembic."""

import os
from collections.abc import Iterator

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from app.core.config import normalize_database_url
from app.db.session import get_db
from app.main import app

TEST_DATABASE_URL = normalize_database_url(
    os.environ.get("TEST_DATABASE_URL", "postgresql+psycopg://localhost/kanban_test")
)
if "test" not in TEST_DATABASE_URL.rsplit("/", 1)[-1]:
    # The fixtures TRUNCATE every table, so refuse anything that is not a test DB.
    msg = "TEST_DATABASE_URL must point at a database whose name contains 'test'"
    raise RuntimeError(msg)
TABLES = "comments, cards, milestones, stages, members, boards"


def alembic_config() -> Config:
    """Return an Alembic config that points at the test database."""
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL.replace("%", "%%"))
    return config


@pytest.fixture(scope="session")
def engine() -> Iterator[Engine]:
    command.upgrade(alembic_config(), "head")
    test_engine = create_engine(TEST_DATABASE_URL)
    yield test_engine
    test_engine.dispose()


@pytest.fixture(autouse=True)
def _clean_tables(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text(f"truncate {TABLES} restart identity cascade"))


@pytest.fixture
def client(engine: Engine) -> Iterator[TestClient]:
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override() -> Iterator[Session]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override
    yield TestClient(app)
    app.dependency_overrides.clear()


API = "/api/v1"


class Api:
    """Small helper that wraps the TestClient with the API prefix."""

    def __init__(self, client: TestClient) -> None:
        self.client = client

    def get(self, path: str, **kwargs):
        return self.client.get(API + path, **kwargs)

    def post(self, path: str, json: dict | None = None):
        return self.client.post(API + path, json=json)

    def patch(self, path: str, json: dict):
        return self.client.patch(API + path, json=json)

    def delete(self, path: str):
        return self.client.delete(API + path)


@pytest.fixture
def api(client: TestClient) -> Api:
    return Api(client)


@pytest.fixture
def board(api: Api) -> dict:
    """A board with the default three stages, members ann and bob, one milestone."""
    created = api.post("/boards", {"name": "Team", "repo_url": "https://x/y"}).json()
    board_id = created["id"]
    api.post(
        f"/boards/{board_id}/members",
        {"github_login": "ann", "name": "Ann", "role": "dev"},
    )
    api.post(f"/boards/{board_id}/members", {"github_login": "bob", "name": "Bob"})
    api.post(f"/boards/{board_id}/milestones", {"title": "M1", "due_on": "2026-12-01"})
    return created
