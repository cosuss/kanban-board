"""CLI tests: Typer's CliRunner talks to the FastAPI app without a server."""

import json
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient
from typer.testing import CliRunner, Result

from app.cli import app as cli_app
from app.main import app as api_app
from tests.conftest import Api

runner = CliRunner()
pytestmark = pytest.mark.usefixtures("client")


@pytest.fixture(autouse=True)
def _wire_cli_to_app(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the CLI call the FastAPI app (with the test database) directly."""

    def get_client(_api_url: str) -> httpx.Client:
        return TestClient(api_app, base_url="http://testserver/api/v1")

    monkeypatch.setattr("app.cli.client.get_client", get_client)
    monkeypatch.delenv("KANBAN_API_URL", raising=False)
    monkeypatch.delenv("KANBAN_BOARD", raising=False)


def run(*args: str) -> Result:
    return runner.invoke(cli_app, list(args))


def run_json(*args: str) -> Any:
    result = run("--json", *args)
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


@pytest.fixture
def card(board: dict, api: Api) -> dict:
    return api.post(
        f"/boards/{board['id']}/cards",
        {"title": "First card", "stage": "Todo", "assignee": "ann"},
    ).json()


# ------------------------------------------------------------ top level


def test_no_args_shows_help() -> None:
    result = runner.invoke(cli_app, [])
    assert "Manage your team's kanban board" in result.output
    for name in ("board", "member", "stage", "milestone", "card", "comment", "view"):
        assert name in result.output


def test_every_command_has_help() -> None:
    groups = {
        "board": ["list", "add", "show", "update", "delete"],
        "member": ["list", "add", "show", "update", "delete"],
        "stage": ["list", "add", "show", "update", "delete"],
        "milestone": ["list", "add", "show", "update", "delete"],
        "card": ["list", "add", "show", "update", "move", "delete"],
        "comment": ["list", "add", "show", "delete"],
        "db": ["upgrade"],
    }
    banned = ("HTTP", "endpoint", "payload", "enum", "pagination")
    commands = [["health"], ["serve"], ["view"]]
    commands += [[group, name] for group, names in groups.items() for name in names]
    for command in commands:
        result = run(*command, "--help")
        assert result.exit_code == 0, command
        assert "Usage" in result.output
        assert not [word for word in banned if word in result.output], command
    for group in groups:
        result = run(group)
        assert "Examples" in result.output, group


def test_health_text_and_json() -> None:
    assert "Server is running. Database: ok." in run("health").stdout
    assert run_json("health") == {"status": "ok", "database": "ok"}


@pytest.mark.usefixtures("board")
def test_global_options_work_after_the_command() -> None:
    result = run("card", "add", "x", "--json")
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["title"] == "x"
    assert run("board", "list", "--json").stdout.lstrip().startswith("[")


def test_unreachable_server_exits_1(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(api_url: str) -> httpx.Client:
        return httpx.Client(base_url=api_url + "/api/v1", timeout=1)

    monkeypatch.setattr("app.cli.client.get_client", refuse)
    result = run("--api-url", "http://127.0.0.1:1/", "health")
    assert result.exit_code == 1
    assert "Cannot reach the kanban server at http://127.0.0.1:1" in result.stderr
    assert "Traceback" not in result.stderr


def test_usage_errors_exit_2() -> None:
    assert run("--board", "abc", "view").exit_code == 2
    assert run("--board", "0", "view").exit_code == 2
    assert run("--api-url", "not-a-url", "health").exit_code == 2
    assert run("card", "show").exit_code == 2
    assert run("card", "show", "x").exit_code == 2
    assert run("card", "nope").exit_code == 2


# -------------------------------------------------------------- boards


def test_board_crud() -> None:
    created = run("board", "add", "Team A", "--repo-url", "https://x/a")
    assert created.exit_code == 0
    assert "Created board 1: Team A" in created.stdout
    assert [b["name"] for b in run_json("board", "list")] == ["Team A"]
    assert "Repo: https://x/a" in run("board", "show", "1").stdout
    assert "Board 1: Team A" in run("board", "show").stdout
    assert "Updated board 1." in run("board", "update", "1", "--name", "B").stdout
    assert run_json("board", "update", "1", "--clear-repo-url")["repo_url"] is None
    assert [s["name"] for s in run_json("stage", "list")] == [
        "Todo",
        "In Progress",
        "Done",
    ]
    deleted = run("board", "delete", "1")
    assert "Deleted board 1 and everything in it." in deleted.stdout
    assert run("--json", "board", "delete", "1").exit_code == 1


def test_board_no_default_stages_and_empty_list() -> None:
    assert "No boards yet" in run("board", "list").stdout
    created = run_json("board", "add", "Bare", "--no-default-stages")
    assert created["name"] == "Bare"
    assert run_json("stage", "list") == []


def test_board_errors() -> None:
    missing = run("board", "show", "99")
    assert missing.exit_code == 1
    assert missing.stderr.strip() == "Error: board not found (404)" or (
        "(404)" in missing.stderr
    )
    assert run("board", "update", "1").exit_code == 2
    both = run("board", "update", "1", "--repo-url", "u", "--clear-repo-url")
    assert both.exit_code == 2
    run("board", "add", "Dup", "--repo-url", "https://x/dup")
    dup = run("board", "add", "Other", "--repo-url", "https://x/dup")
    assert dup.exit_code == 1
    assert "(409)" in dup.stderr


# ------------------------------------------------- members and milestones


@pytest.mark.usefixtures("board")
def test_member_commands() -> None:
    added = run("member", "add", "codex", "--name", "Codex", "--role", "AI")
    assert "Added member codex (id 3)." in added.stdout
    assert {m["github_login"] for m in run_json("member", "list")} == {
        "ann",
        "bob",
        "codex",
    }
    assert "Role: AI" in run("member", "show", "3").stdout
    assert run_json("member", "update", "3", "--clear-role")["role"] is None
    assert run_json("member", "update", "3", "--name", "C2")["name"] == "C2"
    assert run("member", "update", "3").exit_code == 2
    assert run("member", "add", "codex").exit_code == 2
    assert run("member", "add", "ann", "--name", "Again").exit_code == 1
    assert "Deleted member 3." in run("member", "delete", "3").stdout
    assert run("member", "show", "3").exit_code == 1


@pytest.mark.usefixtures("board")
def test_stage_commands() -> None:
    added = run("stage", "add", "Review", "--position", "4")
    assert 'Added stage "Review" (id 4, position 4).' in added.stdout
    assert "Stage 4: Review (position 4)" in run("stage", "show", "4").stdout
    assert run_json("stage", "update", "4", "--name", "QA")["name"] == "QA"
    assert run("stage", "update", "4").exit_code == 2
    assert "ID" in run("stage", "list").stdout
    assert "Deleted stage 4." in run("stage", "delete", "4").stdout
    assert run("stage", "show", "4").exit_code == 1


def test_stage_with_cards_cannot_be_deleted(card: dict) -> None:
    result = run("stage", "delete", str(card["stage_id"]))
    assert result.exit_code == 1
    assert "(409)" in result.stderr


@pytest.mark.usefixtures("board")
def test_milestone_commands() -> None:
    added = run("milestone", "add", "MVP", "--due-on", "2026-11-01")
    assert 'Added milestone "MVP" (id 2).' in added.stdout
    assert "Due: 2026-11-01" in run("milestone", "show", "2").stdout
    assert "MVP" in run("milestone", "list").stdout
    assert run_json("milestone", "update", "2", "--clear-due-on")["due_on"] is None
    updated = run_json("milestone", "update", "2", "--due-on", "2026-12-24")
    assert updated["due_on"] == "2026-12-24"
    assert run("milestone", "update", "2").exit_code == 2
    assert run("milestone", "add", "Bad", "--due-on", "soon").exit_code == 2
    assert "Deleted milestone 2." in run("milestone", "delete", "2").stdout
    assert run("milestone", "show", "2").exit_code == 1


# --------------------------------------------------------------- cards


@pytest.mark.usefixtures("board")
def test_card_add_resolves_names_and_prints_a_sentence() -> None:
    result = run(
        "card",
        "add",
        "Login API",
        "--stage",
        "In Progress",
        "--assignee",
        "ann",
        "--milestone",
        "M1",
        "--body",
        "plan",
    )
    assert result.exit_code == 0, result.output
    assert "Created card 1 (issue #1) in In Progress: Login API" in result.stdout
    data = run_json("card", "show", "1")
    assert (data["stage"], data["assignee"], data["milestone"], data["body"]) == (
        "In Progress",
        "ann",
        "M1",
        "plan",
    )
    for key in ("id", "issue_number", "position", "created_at", "closed_at"):
        assert key in data


@pytest.mark.usefixtures("board")
def test_card_add_defaults_to_first_stage_and_accepts_ids() -> None:
    first = run_json("card", "add", "plain")
    assert first["stage"] == "Todo"
    by_id = run_json(
        "card", "add", "by id", "--stage-id", "2", "--assignee-id", "2",
        "--milestone-id", "1", "--issue-number", "40",
    )  # fmt: skip
    assert (by_id["stage"], by_id["assignee"], by_id["issue_number"]) == (
        "In Progress",
        "bob",
        40,
    )


@pytest.mark.usefixtures("board")
def test_card_add_errors() -> None:
    assert run("card", "add").exit_code == 2
    both = run("card", "add", "x", "--stage", "Todo", "--stage-id", "1")
    assert both.exit_code == 2
    assert (
        run("card", "add", "x", "--assignee", "a", "--assignee-id", "1").exit_code == 2
    )
    unknown = run("card", "add", "x", "--stage", "Nope")
    assert unknown.exit_code == 1
    assert "(404)" in unknown.stderr
    run("card", "add", "a", "--issue-number", "5")
    dup = run("card", "add", "b", "--issue-number", "5")
    assert dup.exit_code == 1
    assert "(409)" in dup.stderr
    assert run("card", "add", "z", "--board", "99").exit_code == 1


@pytest.mark.usefixtures("board")
def test_card_list_filters_and_paging() -> None:
    run("card", "add", "Login page", "--stage", "Todo", "--assignee", "ann")
    run("card", "add", "Logout", "--stage", "Done", "--assignee", "bob")
    run("card", "add", "Docs", "--stage", "Todo", "--milestone", "M1")
    assert len(run_json("card", "list")) == 3
    assert len(run_json("card", "list", "--stage", "Todo")) == 2
    assert len(run_json("card", "list", "--assignee", "bob")) == 1
    assert len(run_json("card", "list", "--milestone", "M1")) == 1
    assert len(run_json("card", "list", "-q", "log")) == 2
    assert len(run_json("card", "list", "--search", "docs")) == 1
    assert len(run_json("card", "list", "--limit", "1", "--offset", "1")) == 1
    text = run("card", "list", "--stage", "Todo")
    assert "Login page" in text.stdout
    assert "Showing 2 cards." in text.stdout
    assert "No cards found." in run("card", "list", "-q", "zzz").stdout
    assert run("card", "list", "--limit", "0").exit_code == 2
    assert run("card", "list", "--limit", "500").exit_code == 2


def test_card_show_text(card: dict) -> None:
    result = run("card", "show", str(card["id"]))
    assert "Card 1 (issue #1): First card" in result.stdout
    assert "Stage:     Todo" in result.stdout
    assert "Assignee:  ann (Ann)" in result.stdout
    assert "Closed:    -" in result.stdout
    assert run("card", "show", "999").exit_code == 1


def test_card_update_and_clear(card: dict) -> None:
    cid = str(card["id"])
    updated = run("card", "update", cid, "--title", "Renamed", "--milestone", "M1")
    assert "Updated card 1." in updated.stdout
    data = run_json("card", "update", cid, "--assignee", "bob", "--body", "text")
    assert (data["assignee"], data["title"], data["milestone"]) == (
        "bob",
        "Renamed",
        "M1",
    )
    cleared = run_json(
        "card", "update", cid, "--clear-assignee", "--clear-milestone", "--clear-body"
    )
    assert cleared["assignee"] is None
    assert cleared["milestone"] is None
    assert cleared["body"] is None
    assert run_json("card", "update", cid, "--stage", "Done")["closed_at"]
    assert run("card", "update", cid).exit_code == 2
    clash = run("card", "update", cid, "--assignee", "ann", "--clear-assignee")
    assert clash.exit_code == 2
    assert run("card", "update", "999", "--title", "x").exit_code == 1


def test_card_move_sets_and_clears_closed_at(card: dict) -> None:
    cid = str(card["id"])
    assert (
        "Moved card 1 to In Progress." in run("card", "move", cid, "In Progress").stdout
    )
    assert run_json("card", "show", cid)["closed_at"] is None
    done = run_json("card", "move", cid, "Done")
    assert done["stage"] == "Done"
    assert done["closed_at"] is not None
    reopened = run_json("card", "move", cid, "--stage-id", "1", "--position", "1")
    assert (reopened["stage"], reopened["closed_at"]) == ("Todo", None)


def test_card_move_errors(card: dict) -> None:
    cid = str(card["id"])
    assert run("card", "move", cid).exit_code == 2
    assert run("card", "move", cid, "Done", "--stage-id", "3").exit_code == 2
    missing = run("card", "move", cid, "Nowhere")
    assert missing.exit_code == 1
    assert "(404)" in missing.stderr
    assert run("card", "move", "999", "Done").exit_code == 1


def test_card_delete(card: dict) -> None:
    cid = str(card["id"])
    result = run("card", "delete", cid)
    assert "Deleted card 1." in result.stdout
    assert run("card", "show", cid).exit_code == 1
    assert run("card", "delete", cid).exit_code == 1


def test_json_delete_prints_nothing(card: dict) -> None:
    result = run("--json", "card", "delete", str(card["id"]))
    assert result.exit_code == 0
    assert not result.stdout


# ------------------------------------------------------------ comments


def test_comment_commands(card: dict) -> None:
    cid = str(card["id"])
    added = run("comment", "add", cid, "Done and tested", "--author", "ann")
    assert "Added comment 1 to card 1." in added.stdout
    run("comment", "add", cid, "anonymous note")
    listed = run("comment", "list", cid)
    assert "ann: Done and tested" in listed.stdout
    assert "-: anonymous note" in listed.stdout
    data = run_json("comment", "list", cid)
    assert [c["body"] for c in data] == ["Done and tested", "anonymous note"]
    shown = run("comment", "show", "1")
    assert "Comment 1 on card 1 by ann" in shown.stdout
    assert "Done and tested" in shown.stdout
    by_id = run_json("comment", "add", cid, "by id", "--author-id", "2")
    assert by_id["author"] == "bob"
    assert "Deleted comment 1." in run("comment", "delete", "1").stdout
    assert run("comment", "show", "1").exit_code == 1


def test_comment_errors(card: dict) -> None:
    cid = str(card["id"])
    assert run("comment", "add", cid).exit_code == 2
    both = run("comment", "add", cid, "x", "--author", "ann", "--author-id", "1")
    assert both.exit_code == 2
    assert run("comment", "add", "999", "x").exit_code == 1
    assert run("comment", "add", cid, "x", "--author", "ghost").exit_code == 1
    assert "No comments yet." in run("comment", "list", cid).stdout


# ---------------------------------------------------------------- view


@pytest.mark.usefixtures("board")
def test_view_text_and_json() -> None:
    run("card", "add", "Login API", "--stage", "Todo", "--assignee", "ann")
    run("card", "add", "Docs", "--stage", "Done")
    text = run("view").stdout
    assert "Board 1: Team" in text
    assert "Todo (1)" in text
    assert "In Progress (0)" in text
    assert "Done (1)" in text
    assert "#1 Login API (ann)" in text
    assert "#2 Docs (-)" in text
    assert "(empty)" in text
    data = run_json("view")
    assert set(data) == {"board", "stages"}
    assert [s["name"] for s in data["stages"]] == ["Todo", "In Progress", "Done"]
    assert data["stages"][0]["cards"][0]["title"] == "Login API"


@pytest.mark.usefixtures("board")
def test_view_handles_korean_and_brackets() -> None:
    run("card", "add", "[긴급] 로그인 화면", "--assignee", "ann")
    assert "[긴급] 로그인 화면" in run("view").stdout
    assert "[긴급] 로그인 화면" in run("card", "list").stdout


def test_view_missing_board() -> None:
    result = run("--board", "42", "view")
    assert result.exit_code == 1
    assert "(404)" in result.stderr


@pytest.mark.usefixtures("board")
def test_board_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KANBAN_BOARD", "77")
    assert run("view").exit_code == 1
    assert run("view", "--board", "1").exit_code == 0


@pytest.mark.usefixtures("board")
def test_json_output_keeps_korean_unescaped() -> None:
    created = run("--json", "card", "add", "한글 제목")
    assert "한글 제목" in created.stdout
    assert "\\u" not in created.stdout


@pytest.mark.usefixtures("board")
def test_api_validation_error_is_one_line() -> None:
    result = run("member", "add", "", "--name", "Nobody")
    assert result.exit_code == 1
    lines = result.stderr.strip().splitlines()
    assert len(lines) == 1
    assert lines[0].startswith("Error: github_login:")
    assert lines[0].endswith("(422)")
