import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.demo import prepare_demo
from app.main import app


def test_browser_preflight(client: TestClient):
    for origin in ("http://localhost:3000", "http://127.0.0.1:3000"):
        response = client.options(
            "/api/v1/boards",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "PATCH",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
    response = client.options(
        "/api/v1/boards",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "DELETE",
        },
    )
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers


def test_demo_rerun_preserves_user_edits(client: TestClient):
    board_id = prepare_demo(client)
    view = client.get(f"/api/v1/boards/{board_id}/view").json()
    cards = [card for stage in view["stages"] for card in stage["cards"]]
    assert len(cards) == 3
    client.patch(f"/api/v1/cards/{cards[0]['id']}", json={"body": "팀원 메모"})
    assert prepare_demo(client) == board_id
    view = client.get(f"/api/v1/boards/{board_id}/view").json()
    cards = [card for stage in view["stages"] for card in stage["cards"]]
    assert len(cards) == 3
    assert any(card["body"] == "팀원 메모" for card in cards)
    assert sum(card["closed_at"] is not None for card in cards) == 1


def test_openapi_snapshot():
    assert (
        json.loads(Path("docs/openapi.json").read_text(encoding="utf-8"))
        == app.openapi()
    )
