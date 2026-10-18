from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.db.session import get_db
from app.main import app
from tests.conftest import Api


def test_health_ok(api: Api, client: TestClient) -> None:
    assert api.get("/health").json() == {"status": "ok", "database": "ok"}
    assert client.get("/health").status_code == 200


def test_health_503_when_database_down(client: TestClient) -> None:
    broken = MagicMock()
    broken.execute.side_effect = OperationalError("select 1", {}, Exception("down"))
    app.dependency_overrides[get_db] = lambda: broken
    response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.json() == {"detail": "database unavailable"}
