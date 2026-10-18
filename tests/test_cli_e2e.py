"""End-to-end CLI test: a real uvicorn server on a throwaway Postgres database."""

import json
import os
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from tests.conftest import TEST_DATABASE_URL

ROOT = Path(__file__).resolve().parents[1]
UV = shutil.which("uv")


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _admin(statement: str) -> None:
    """Run CREATE/DROP DATABASE on the server that hosts the test database."""
    engine = create_engine(TEST_DATABASE_URL, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        connection.execute(text(statement))
    engine.dispose()


@pytest.fixture
def e2e_env() -> Iterator[dict[str, str]]:
    """Environment with DATABASE_URL pointing at a temporary database."""
    name = f"kanban_e2e_{os.getpid()}"
    _admin(f'create database "{name}"')
    url = make_url(TEST_DATABASE_URL).set(database=name)
    environment = os.environ.copy()
    environment["DATABASE_URL"] = url.render_as_string(hide_password=False)
    try:
        yield environment
    finally:
        _admin(f'drop database if exists "{name}" with (force)')


@pytest.fixture
def api_url(e2e_env: dict[str, str]) -> Iterator[str]:
    """Migrate the temporary database with the CLI and start a real server."""
    if UV is None:
        pytest.skip("uv is required to run the CLI entry point")
    migrated = subprocess.run(
        [UV, "run", "--locked", "kanban", "db", "upgrade"],
        cwd=ROOT,
        env=e2e_env,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )
    assert migrated.returncode == 0, migrated.stderr
    assert "Database is up to date." in migrated.stdout

    port = _free_port()
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "error",
        ],
        cwd=ROOT,
        env=e2e_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if server.poll() is not None:
                pytest.fail("API server exited before becoming ready")
            try:
                if httpx.get(f"{base}/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.1)
        else:
            pytest.fail("API server did not become ready within 20 seconds")
        yield base
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)


def _kanban(
    base_url: str, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    assert UV is not None
    environment = dict(env or os.environ)
    environment["KANBAN_API_URL"] = base_url
    return subprocess.run(
        [UV, "run", "--locked", "kanban", *args],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
        timeout=60,
    )


def _json(base_url: str, *args: str) -> object:
    result = _kanban(base_url, *args, "--json")
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_codex_workflow_end_to_end(api_url: str) -> None:
    assert _json(api_url, "health") == {"status": "ok", "database": "ok"}

    board = _json(api_url, "board", "add", "E2E Team")
    board_id = str(board["id"])
    options = ("--board", board_id)

    member = _json(
        api_url, "member", "add", "codex", "--name", "Codex 에이전트", *options
    )
    assert member["github_login"] == "codex"

    stages = _json(api_url, "stage", "list", *options)
    assert [s["name"] for s in stages] == ["Todo", "In Progress", "Done"]

    milestone = _json(
        api_url, "milestone", "add", "MVP", "--due-on", "2026-11-01", *options
    )
    assert milestone["title"] == "MVP"

    card = _json(
        api_url, "card", "add", "로그인 API 구현", "--stage", "Todo",
        "--assignee", "codex", "--milestone", "MVP", "--body", "plan", *options,
    )  # fmt: skip
    assert card["assignee"] == "codex"
    assert card["closed_at"] is None
    card_id = str(card["id"])

    moved = _json(api_url, "card", "move", card_id, "In Progress")
    assert moved["stage"] == "In Progress"

    comment = _json(
        api_url, "comment", "add", card_id, "구현 완료", "--author", "codex"
    )
    assert comment["author"] == "codex"

    done = _json(api_url, "card", "move", card_id, "Done")
    assert done["stage"] == "Done"
    assert done["closed_at"] is not None

    view = _json(api_url, "view", *options)
    columns = {s["name"]: s["cards"] for s in view["stages"]}
    assert [c["id"] for c in columns["Done"]] == [int(card_id)]

    text_view = _kanban(api_url, "view", *options)
    assert text_view.returncode == 0, text_view.stderr
    assert "로그인 API 구현 (codex)" in text_view.stdout

    deleted = _kanban(api_url, "card", "delete", card_id)
    assert deleted.returncode == 0, deleted.stderr
    missing = _kanban(api_url, "card", "show", card_id)
    assert missing.returncode == 1
    assert "(404)" in missing.stderr

    board_deleted = _kanban(api_url, "board", "delete", board_id)
    assert board_deleted.returncode == 0, board_deleted.stderr
    assert _kanban(api_url, "board", "show", board_id).returncode == 1


def test_help_runs_without_a_server() -> None:
    if UV is None:
        pytest.skip("uv is required")
    result = _kanban("http://127.0.0.1:1", "--help")
    assert result.returncode == 0
    assert "Manage your team's kanban board" in result.stdout
    unreachable = _kanban("http://127.0.0.1:1", "health")
    assert unreachable.returncode == 1
    assert "Cannot reach the kanban server" in unreachable.stderr
