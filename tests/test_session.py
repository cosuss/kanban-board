"""Session dependency (slot limiter, 503) and DataError mapping."""

import pytest
from anyio import CapacityLimiter
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from app.db import session as session_module
from app.main import app
from tests.conftest import Api


@pytest.fixture
def real_get_db(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    """Use the real ``get_db`` but bound to the test database."""
    monkeypatch.setattr(
        session_module,
        "SessionLocal",
        sessionmaker(bind=engine, expire_on_commit=False),
    )
    app.dependency_overrides.clear()


def test_real_get_db_serves_and_releases_slot(
    real_get_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    del real_get_db
    slots = CapacityLimiter(1)
    monkeypatch.setattr(session_module, "_SESSION_SLOTS", slots)
    with TestClient(app) as client:
        for _ in range(3):  # a leaked slot would hang or 503 the second call
            assert client.get("/health").status_code == 200
    assert slots.borrowed_tokens == 0


def test_busy_pool_answers_503_not_500(
    real_get_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    del real_get_db
    slots = CapacityLimiter(0)  # every slot is taken by someone else
    monkeypatch.setattr(session_module, "_SESSION_SLOTS", slots)
    settings = session_module.get_settings().model_copy(
        update={"database_pool_timeout": 0.05}
    )
    monkeypatch.setattr(session_module, "get_settings", lambda: settings)
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {"detail": "database busy, try again"}


def test_out_of_range_numbers_are_422(api: Api) -> None:
    board = api.post("/boards", {"name": "b"}).json()
    too_big = 99_999_999_999_999_999_999
    assert api.get(f"/cards/{too_big}").status_code == 422
    response = api.post(
        f"/boards/{board['id']}/cards", {"title": "x", "issue_number": too_big}
    )
    assert response.status_code == 422


def test_nul_character_is_422(api: Api) -> None:
    board = api.post("/boards", {"name": "b"}).json()
    response = api.post(f"/boards/{board['id']}/cards", {"title": "a\x00b"})
    assert response.status_code == 422
