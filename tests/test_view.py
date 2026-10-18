from tests.conftest import Api


def test_view_orders_stages_and_cards(api: Api, board: dict) -> None:
    board_id = board["id"]
    for title, stage in [
        ("t1", "Todo"),
        ("d1", "Done"),
        ("t2", "Todo"),
        ("p1", "In Progress"),
    ]:
        api.post(f"/boards/{board_id}/cards", {"title": title, "stage": stage})
    data = api.get(f"/boards/{board_id}/view").json()
    assert data["board"]["id"] == board_id
    assert [s["name"] for s in data["stages"]] == ["Todo", "In Progress", "Done"]
    assert [[c["title"] for c in s["cards"]] for s in data["stages"]] == [
        ["t1", "t2"],
        ["p1"],
        ["d1"],
    ]
    assert data["stages"][0]["cards"][0]["stage"] == "Todo"


def test_view_reflects_stage_reordering(api: Api, board: dict) -> None:
    board_id = board["id"]
    api.post(f"/boards/{board_id}/cards", {"title": "a"})
    stages = api.get(f"/boards/{board_id}/stages").json()
    api.patch(f"/stages/{stages[2]['id']}", {"position": 10})
    api.patch(f"/stages/{stages[0]['id']}", {"position": 11})
    data = api.get(f"/boards/{board_id}/view").json()
    assert [s["name"] for s in data["stages"]] == ["In Progress", "Done", "Todo"]


def test_view_empty_and_404(api: Api, board: dict) -> None:
    data = api.get(f"/boards/{board['id']}/view").json()
    assert all(s["cards"] == [] for s in data["stages"])
    assert api.get("/boards/999/view").status_code == 404
