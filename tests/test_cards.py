from tests.conftest import Api


def _add(api: Api, board_id: int, title: str, **extra) -> dict:
    response = api.post(f"/boards/{board_id}/cards", {"title": title, **extra})
    assert response.status_code == 201, response.text
    return response.json()


def test_create_card_defaults(api: Api, board: dict) -> None:
    card = _add(api, board["id"], "first")
    assert card["issue_number"] == 1
    assert card["stage"] == "Todo"
    assert card["position"] == 1
    assert card["board_id"] == board["id"]
    assert card["assignee"] is None
    assert card["closed_at"] is None
    assert card["created_at"]


def test_card_by_names_fills_both_name_and_id(api: Api, board: dict) -> None:
    card = _add(
        api,
        board["id"],
        "t",
        stage="In Progress",
        assignee="ann",
        milestone="M1",
        body="hello",
    )
    assert card["stage"] == "In Progress"
    assert (card["assignee"], card["assignee_name"]) == ("ann", "Ann")
    assert card["milestone"] == "M1"
    assert card["body"] == "hello"
    same = _add(
        api,
        board["id"],
        "u",
        stage_id=card["stage_id"],
        assignee_id=card["assignee_id"],
        milestone_id=card["milestone_id"],
    )
    assert (same["stage"], same["assignee"], same["milestone"]) == (
        "In Progress",
        "ann",
        "M1",
    )


def test_issue_numbers_auto_increment_and_explicit(api: Api, board: dict) -> None:
    numbers = [_add(api, board["id"], str(i))["issue_number"] for i in range(3)]
    assert numbers == [1, 2, 3]
    assert _add(api, board["id"], "gh", issue_number=50)["issue_number"] == 50
    assert _add(api, board["id"], "next")["issue_number"] == 51


def test_duplicate_issue_number_is_409(api: Api, board: dict) -> None:
    _add(api, board["id"], "a", issue_number=7)
    response = api.post(
        f"/boards/{board['id']}/cards", {"title": "b", "issue_number": 7}
    )
    assert response.status_code == 409


def test_issue_numbers_are_global_across_boards(api: Api, board: dict) -> None:
    other = api.post("/boards", {"name": "O"}).json()["id"]
    _add(api, board["id"], "a")
    assert _add(api, other, "b")["issue_number"] == 2


def test_position_auto_per_stage(api: Api, board: dict) -> None:
    first = _add(api, board["id"], "a")
    second = _add(api, board["id"], "b")
    other_stage = _add(api, board["id"], "c", stage="Done")
    assert (first["position"], second["position"], other_stage["position"]) == (1, 2, 1)


def test_move_without_position_goes_to_end(api: Api, board: dict) -> None:
    a = _add(api, board["id"], "a")
    _add(api, board["id"], "b", stage="In Progress")
    _add(api, board["id"], "c", stage="In Progress")
    moved = api.post(f"/cards/{a['id']}/move", {"stage": "In Progress"}).json()
    assert moved["stage"] == "In Progress"
    assert moved["position"] == 3


def test_move_with_position_pushes_others(api: Api, board: dict) -> None:
    board_id = board["id"]
    a = _add(api, board_id, "a", stage="Done")
    b = _add(api, board_id, "b", stage="Done")
    mover = _add(api, board_id, "m")
    moved = api.post(f"/cards/{mover['id']}/move", {"stage": "Done", "position": 1})
    assert moved.json()["position"] == 1
    assert api.get(f"/cards/{a['id']}").json()["position"] == 2
    assert api.get(f"/cards/{b['id']}").json()["position"] == 3
    titles = [
        c["title"]
        for c in api.get(f"/boards/{board_id}/cards", params={"stage": "Done"}).json()
    ]
    assert titles == ["m", "a", "b"]


def test_move_by_stage_id(api: Api, board: dict) -> None:
    card = _add(api, board["id"], "a")
    stage_id = api.get(f"/boards/{board['id']}/stages").json()[1]["id"]
    moved = api.post(f"/cards/{card['id']}/move", {"stage_id": stage_id}).json()
    assert moved["stage"] == "In Progress"


def test_closed_at_set_on_last_stage_and_cleared_when_leaving(
    api: Api, board: dict
) -> None:
    card = _add(api, board["id"], "a")
    done = api.post(f"/cards/{card['id']}/move", {"stage": "Done"}).json()
    assert done["closed_at"] is not None
    again = api.post(f"/cards/{card['id']}/move", {"stage": "Done"}).json()
    assert again["closed_at"] == done["closed_at"]
    reopened = api.post(f"/cards/{card['id']}/move", {"stage": "Todo"}).json()
    assert reopened["closed_at"] is None


def test_closed_at_set_when_created_in_last_stage(api: Api, board: dict) -> None:
    assert _add(api, board["id"], "a", stage="Done")["closed_at"] is not None


def test_last_stage_is_by_position_not_name(api: Api, board: dict) -> None:
    board_id = board["id"]
    api.post(f"/boards/{board_id}/stages", {"name": "Shipped"})
    card = _add(api, board_id, "a")
    assert (
        api.post(f"/cards/{card['id']}/move", {"stage": "Done"}).json()["closed_at"]
        is None
    )
    assert api.post(f"/cards/{card['id']}/move", {"stage": "Shipped"}).json()[
        "closed_at"
    ]


def test_patch_stage_moves_and_syncs_closed_at(api: Api, board: dict) -> None:
    card = _add(api, board["id"], "a")
    done = api.patch(f"/cards/{card['id']}", {"stage": "Done"}).json()
    assert done["closed_at"] is not None
    back = api.patch(f"/cards/{card['id']}", {"stage": "Todo"}).json()
    assert back["closed_at"] is None


def test_patch_fields_and_clearing(api: Api, board: dict) -> None:
    card = _add(api, board["id"], "a", assignee="ann", milestone="M1", body="x")
    updated = api.patch(
        f"/cards/{card['id']}", {"title": "A2", "assignee": "bob", "body": None}
    ).json()
    assert (updated["title"], updated["assignee"], updated["body"]) == (
        "A2",
        "bob",
        None,
    )
    assert updated["milestone"] == "M1"
    cleared = api.patch(
        f"/cards/{card['id']}", {"assignee_id": None, "milestone_id": None}
    ).json()
    assert cleared["assignee"] is None
    assert cleared["milestone"] is None


def test_name_and_id_together_is_422(api: Api, board: dict) -> None:
    path = f"/boards/{board['id']}/cards"
    assert (
        api.post(path, {"title": "t", "stage": "Todo", "stage_id": 1}).status_code
        == 422
    )
    assert (
        api.post(path, {"title": "t", "assignee": "ann", "assignee_id": 1}).status_code
        == 422
    )
    assert (
        api.post(path, {"title": "t", "milestone": "M1", "milestone_id": 1}).status_code
        == 422
    )
    card = _add(api, board["id"], "a")
    assert (
        api.patch(f"/cards/{card['id']}", {"stage": "Todo", "stage_id": 1}).status_code
        == 422
    )


def test_unknown_names_are_404(api: Api, board: dict) -> None:
    path = f"/boards/{board['id']}/cards"
    assert api.post(path, {"title": "t", "stage": "Nope"}).status_code == 404
    assert api.post(path, {"title": "t", "assignee": "ghost"}).status_code == 404
    assert api.post(path, {"title": "t", "milestone": "Nope"}).status_code == 404
    assert api.post(path, {"title": "t", "stage_id": 999}).status_code == 404
    card = _add(api, board["id"], "a")
    assert api.patch(f"/cards/{card['id']}", {"assignee": "ghost"}).status_code == 404
    assert api.post(f"/cards/{card['id']}/move", {"stage": "Nope"}).status_code == 404


def test_member_from_other_board_is_404(api: Api, board: dict) -> None:
    other = api.post("/boards", {"name": "O"}).json()["id"]
    api.post(f"/boards/{other}/members", {"github_login": "zed", "name": "Zed"})
    response = api.post(
        f"/boards/{board['id']}/cards", {"title": "t", "assignee": "zed"}
    )
    assert response.status_code == 404


def test_move_requires_exactly_one_target(api: Api, board: dict) -> None:
    card = _add(api, board["id"], "a")
    path = f"/cards/{card['id']}/move"
    assert api.post(path, {}).status_code == 422
    assert api.post(path, {"stage": "Done", "stage_id": 3}).status_code == 422
    assert api.post(path, {"stage": "Done", "position": 0}).status_code == 422


def test_card_validation_and_404(api: Api, board: dict) -> None:
    path = f"/boards/{board['id']}/cards"
    assert api.post(path, {"title": ""}).status_code == 422
    assert api.post(path, {}).status_code == 422
    assert api.post(path, {"title": "t", "issue_number": 0}).status_code == 422
    assert api.post("/boards/999/cards", {"title": "t"}).status_code == 404
    assert api.get("/cards/999").status_code == 404
    assert api.patch("/cards/999", {"title": "x"}).status_code == 404
    assert api.post("/cards/999/move", {"stage": "Todo"}).status_code == 404
    assert api.delete("/cards/999").status_code == 404


def test_create_card_on_board_without_stages_is_422(api: Api) -> None:
    empty = api.post("/boards", {"name": "E", "with_default_stages": False}).json()[
        "id"
    ]
    assert api.post(f"/boards/{empty}/cards", {"title": "t"}).status_code == 422


def test_delete_card_removes_comments(api: Api, board: dict) -> None:
    card = _add(api, board["id"], "a")
    comment = api.post(f"/cards/{card['id']}/comments", {"body": "hi"}).json()
    assert api.delete(f"/cards/{card['id']}").status_code == 204
    assert api.get(f"/cards/{card['id']}").status_code == 404
    assert api.get(f"/comments/{comment['id']}").status_code == 404


def test_filters(api: Api, board: dict) -> None:
    board_id = board["id"]
    _add(api, board_id, "Fix login bug", assignee="ann", milestone="M1", body="oauth")
    _add(api, board_id, "Write docs", assignee="bob", stage="In Progress")
    _add(api, board_id, "100% done_ok", stage="Done")
    path = f"/boards/{board_id}/cards"

    def titles(**params) -> list[str]:
        response = api.get(path, params=params)
        assert response.status_code == 200
        return [c["title"] for c in response.json()]

    assert len(titles()) == 3
    assert titles(stage="Done") == ["100% done_ok"]
    assert titles(assignee="ann") == ["Fix login bug"]
    assert titles(milestone="M1") == ["Fix login bug"]
    assert titles(q="LOGIN") == ["Fix login bug"]
    assert titles(q="oauth") == ["Fix login bug"]
    assert titles(q="100%") == ["100% done_ok"]
    assert titles(q="%") == ["100% done_ok"]
    assert titles(stage="Todo", assignee="bob") == []
    assert titles(stage="Nope") == []
    assert titles(stage="Todo", q="docs") == []


def test_pagination(api: Api, board: dict) -> None:
    board_id = board["id"]
    for i in range(5):
        _add(api, board_id, f"c{i}")
    path = f"/boards/{board_id}/cards"
    assert [c["title"] for c in api.get(path, params={"limit": 2}).json()] == [
        "c0",
        "c1",
    ]
    page = api.get(path, params={"limit": 2, "offset": 3}).json()
    assert [c["title"] for c in page] == ["c3", "c4"]
    assert api.get(path, params={"limit": 0}).status_code == 422
    assert api.get(path, params={"limit": 201}).status_code == 422
    assert api.get(path, params={"offset": -1}).status_code == 422
    assert api.get("/boards/999/cards").status_code == 404
