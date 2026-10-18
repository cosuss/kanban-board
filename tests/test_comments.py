from tests.conftest import Api


def _card(api: Api, board: dict) -> int:
    return api.post(f"/boards/{board['id']}/cards", {"title": "t"}).json()["id"]


def test_comment_create_list_get_delete(api: Api, board: dict) -> None:
    card_id = _card(api, board)
    created = api.post(f"/cards/{card_id}/comments", {"body": "first", "author": "ann"})
    assert created.status_code == 201
    body = created.json()
    assert (body["author"], body["author_name"], body["body"]) == (
        "ann",
        "Ann",
        "first",
    )
    assert body["created_at"]
    second = api.post(f"/cards/{card_id}/comments", {"body": "second"}).json()
    assert second["author"] is None
    listed = api.get(f"/cards/{card_id}/comments").json()
    assert [c["body"] for c in listed] == ["first", "second"]
    assert api.get(f"/comments/{body['id']}").json()["id"] == body["id"]
    assert api.delete(f"/comments/{body['id']}").status_code == 204
    assert api.get(f"/comments/{body['id']}").status_code == 404


def test_comment_author_by_id(api: Api, board: dict) -> None:
    card_id = _card(api, board)
    ann = api.get(f"/boards/{board['id']}/members").json()[0]
    comment = api.post(
        f"/cards/{card_id}/comments", {"body": "x", "author_id": ann["id"]}
    ).json()
    assert comment["author"] == "ann"


def test_comment_errors(api: Api, board: dict) -> None:
    card_id = _card(api, board)
    path = f"/cards/{card_id}/comments"
    assert api.post(path, {"body": ""}).status_code == 422
    assert api.post(path, {}).status_code == 422
    assert (
        api.post(path, {"body": "x", "author": "ann", "author_id": 1}).status_code
        == 422
    )
    assert api.post(path, {"body": "x", "author": "ghost"}).status_code == 404
    assert api.post("/cards/999/comments", {"body": "x"}).status_code == 404
    assert api.get("/cards/999/comments").status_code == 404
    assert api.get("/comments/999").status_code == 404
    assert api.delete("/comments/999").status_code == 404


def test_deleting_author_keeps_comment(api: Api, board: dict) -> None:
    card_id = _card(api, board)
    comment = api.post(
        f"/cards/{card_id}/comments", {"body": "x", "author": "ann"}
    ).json()
    api.delete(f"/members/{comment['author_id']}")
    after = api.get(f"/comments/{comment['id']}").json()
    assert (after["author_id"], after["author"], after["author_name"]) == (
        None,
        None,
        None,
    )
