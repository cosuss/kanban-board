from tests.conftest import Api


def test_create_board_makes_default_stages(api: Api) -> None:
    response = api.post("/boards", {"name": "B"})
    assert response.status_code == 201
    board_id = response.json()["id"]
    stages = api.get(f"/boards/{board_id}/stages").json()
    assert [(s["name"], s["position"]) for s in stages] == [
        ("Todo", 1),
        ("In Progress", 2),
        ("Done", 3),
    ]


def test_create_board_without_default_stages(api: Api) -> None:
    board_id = api.post("/boards", {"name": "B", "with_default_stages": False}).json()[
        "id"
    ]
    assert api.get(f"/boards/{board_id}/stages").json() == []


def test_board_crud(api: Api) -> None:
    board_id = api.post("/boards", {"name": "B"}).json()["id"]
    assert api.get("/boards").json()[0]["name"] == "B"
    assert api.get(f"/boards/{board_id}").json()["repo_url"] is None
    updated = api.patch(f"/boards/{board_id}", {"name": "C", "repo_url": "u"}).json()
    assert (updated["name"], updated["repo_url"]) == ("C", "u")
    cleared = api.patch(f"/boards/{board_id}", {"repo_url": None}).json()
    assert cleared["repo_url"] is None
    assert api.delete(f"/boards/{board_id}").status_code == 204
    assert api.get(f"/boards/{board_id}").status_code == 404


def test_board_errors(api: Api) -> None:
    assert api.get("/boards/999").status_code == 404
    assert api.get("/boards/999").json() == {"detail": "board 999 not found"}
    assert api.patch("/boards/999", {"name": "x"}).status_code == 404
    assert api.delete("/boards/999").status_code == 404
    assert api.post("/boards", {"name": ""}).status_code == 422
    assert api.post("/boards", {}).status_code == 422
    assert api.get("/boards/abc").status_code == 422


def test_duplicate_repo_url_is_409(api: Api) -> None:
    api.post("/boards", {"name": "A", "repo_url": "u"})
    assert api.post("/boards", {"name": "B", "repo_url": "u"}).status_code == 409
    other = api.post("/boards", {"name": "B", "repo_url": "v"}).json()["id"]
    assert api.patch(f"/boards/{other}", {"repo_url": "u"}).status_code == 409


def test_delete_board_removes_cards_and_children(api: Api, board: dict) -> None:
    board_id = board["id"]
    card = api.post(f"/boards/{board_id}/cards", {"title": "t", "assignee": "ann"})
    card_id = card.json()["id"]
    api.post(f"/cards/{card_id}/comments", {"body": "hi", "author": "ann"})
    assert api.delete(f"/boards/{board_id}").status_code == 204
    assert api.get(f"/cards/{card_id}").status_code == 404
    assert api.get(f"/boards/{board_id}/members").status_code == 404
    assert api.get(f"/boards/{board_id}/cards").status_code == 404


def test_delete_board_keeps_other_boards(api: Api, board: dict) -> None:
    other = api.post("/boards", {"name": "Other"}).json()["id"]
    api.post(f"/boards/{other}/cards", {"title": "keep"})
    api.post(f"/boards/{board['id']}/cards", {"title": "gone"})
    api.delete(f"/boards/{board['id']}")
    assert [c["title"] for c in api.get(f"/boards/{other}/cards").json()] == ["keep"]
