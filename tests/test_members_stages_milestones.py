from tests.conftest import Api


def test_member_crud_and_errors(api: Api, board: dict) -> None:
    board_id = board["id"]
    members = api.get(f"/boards/{board_id}/members").json()
    assert [m["github_login"] for m in members] == ["ann", "bob"]
    member_id = members[0]["id"]
    assert api.get(f"/members/{member_id}").json()["role"] == "dev"
    updated = api.patch(f"/members/{member_id}", {"name": "Anna", "role": None}).json()
    assert (updated["name"], updated["role"]) == ("Anna", None)
    dup = api.post(f"/boards/{board_id}/members", {"github_login": "ann", "name": "x"})
    assert dup.status_code == 409
    assert (
        api.patch(f"/members/{member_id}", {"github_login": "bob"}).status_code == 409
    )
    assert api.post(f"/boards/{board_id}/members", {"name": "x"}).status_code == 422
    assert (
        api.post("/boards/999/members", {"github_login": "z", "name": "z"}).status_code
        == 404
    )
    assert api.get("/members/999").status_code == 404
    assert api.delete(f"/members/{member_id}").status_code == 204
    assert api.delete(f"/members/{member_id}").status_code == 404


def test_deleting_member_clears_assignee_on_cards(api: Api, board: dict) -> None:
    card = api.post(f"/boards/{board['id']}/cards", {"title": "t", "assignee": "ann"})
    api.delete(f"/members/{card.json()['assignee_id']}")
    after = api.get(f"/cards/{card.json()['id']}").json()
    assert after["assignee_id"] is None
    assert after["assignee"] is None


def test_stage_crud_and_position(api: Api, board: dict) -> None:
    board_id = board["id"]
    created = api.post(f"/boards/{board_id}/stages", {"name": "Review"})
    assert created.status_code == 201
    assert created.json()["position"] == 4
    explicit = api.post(
        f"/boards/{board_id}/stages", {"name": "Blocked", "position": 9}
    )
    assert explicit.json()["position"] == 9
    stage_id = created.json()["id"]
    renamed = api.patch(f"/stages/{stage_id}", {"name": "QA", "position": 5}).json()
    assert (renamed["name"], renamed["position"]) == ("QA", 5)
    names = [s["name"] for s in api.get(f"/boards/{board_id}/stages").json()]
    assert names == ["Todo", "In Progress", "Done", "QA", "Blocked"]
    assert api.get(f"/stages/{stage_id}").status_code == 200


def test_stage_conflicts_and_validation(api: Api, board: dict) -> None:
    board_id = board["id"]
    assert api.post(f"/boards/{board_id}/stages", {"name": "Todo"}).status_code == 409
    assert (
        api.post(f"/boards/{board_id}/stages", {"name": "X", "position": 1}).status_code
        == 409
    )
    assert (
        api.post(f"/boards/{board_id}/stages", {"name": "X", "position": 0}).status_code
        == 422
    )
    assert api.get("/stages/999").status_code == 404
    assert api.post("/boards/999/stages", {"name": "X"}).status_code == 404


def test_delete_stage_with_cards_is_409(api: Api, board: dict) -> None:
    board_id = board["id"]
    api.post(f"/boards/{board_id}/cards", {"title": "t"})
    todo = api.get(f"/boards/{board_id}/stages").json()[0]["id"]
    response = api.delete(f"/stages/{todo}")
    assert response.status_code == 409
    assert "card" in response.json()["detail"]


def test_delete_empty_stage(api: Api, board: dict) -> None:
    in_progress = api.get(f"/boards/{board['id']}/stages").json()[1]["id"]
    assert api.delete(f"/stages/{in_progress}").status_code == 204
    assert api.delete(f"/stages/{in_progress}").status_code == 404


def test_milestone_crud_and_errors(api: Api, board: dict) -> None:
    board_id = board["id"]
    milestones = api.get(f"/boards/{board_id}/milestones").json()
    assert milestones[0]["due_on"] == "2026-12-01"
    milestone_id = milestones[0]["id"]
    assert api.get(f"/milestones/{milestone_id}").json()["title"] == "M1"
    updated = api.patch(
        f"/milestones/{milestone_id}", {"title": "M2", "due_on": None}
    ).json()
    assert (updated["title"], updated["due_on"]) == ("M2", None)
    api.post(f"/boards/{board_id}/milestones", {"title": "M3"})
    dup = api.post(f"/boards/{board_id}/milestones", {"title": "M3"})
    assert dup.status_code == 409
    assert (
        api.post(
            f"/boards/{board_id}/milestones", {"title": "x", "due_on": "nope"}
        ).status_code
        == 422
    )
    assert api.get("/milestones/999").status_code == 404
    assert api.delete(f"/milestones/{milestone_id}").status_code == 204


def test_deleting_milestone_clears_it_on_cards(api: Api, board: dict) -> None:
    card = api.post(f"/boards/{board['id']}/cards", {"title": "t", "milestone": "M1"})
    assert card.json()["milestone"] == "M1"
    api.delete(f"/milestones/{card.json()['milestone_id']}")
    assert api.get(f"/cards/{card.json()['id']}").json()["milestone"] is None
