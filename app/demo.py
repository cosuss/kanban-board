"""Prepare a reusable example board through the HTTP API, without deleting data."""

import os
import sys
from typing import Any

import httpx

# JSON responses contain heterogeneous values.
# ruff: file-ignore[any-type]

DEMO_REPO = "https://example.com/kanban-handoff-demo"


def _request(client: httpx.Client, method: str, path: str, **kwargs: Any) -> Any:
    response = client.request(method, f"/api/v1{path}", **kwargs)
    response.raise_for_status()
    return response.json()


def prepare_demo(client: httpx.Client) -> int:
    """Fill missing demo items and return the actual board ID; reruns are safe."""
    boards = _request(client, "GET", "/boards")
    board = next((b for b in boards if b["repo_url"] == DEMO_REPO), None)
    if board is None:
        board = _request(
            client,
            "POST",
            "/boards",
            json={"name": "프론트엔드 연동 예제", "repo_url": DEMO_REPO},
        )
    board_id = board["id"]
    base = f"/boards/{board_id}"
    stages = _request(client, "GET", f"{base}/stages")
    for name in ("Todo", "In Progress", "Done"):
        if not any(stage["name"] == name for stage in stages):
            _request(client, "POST", f"{base}/stages", json={"name": name})
    members = _request(client, "GET", f"{base}/members")
    login = f"handoff-demo-{board_id}"
    if not any(member["github_login"] == login for member in members):
        _request(
            client,
            "POST",
            f"{base}/members",
            json={"github_login": login, "name": "예제 팀원"},
        )
    view = _request(client, "GET", f"{base}/view")
    titles = {card["title"] for stage in view["stages"] for card in stage["cards"]}
    for stage, title in (
        ("Todo", "[예제] 팀 업무 등록하기"),
        ("In Progress", "[예제] 프론트엔드 연결하기"),
        ("Done", "[예제] 백엔드 실행 확인하기"),
    ):
        if title not in titles:
            _request(
                client,
                "POST",
                f"{base}/cards",
                json={"title": title, "stage": stage, "assignee": login},
            )
    return board_id


def main() -> None:
    """Prepare examples on the selected API and print frontend configuration."""
    base = os.environ.get("KANBAN_API_URL", "http://127.0.0.1:8000").rstrip("/")
    try:
        with httpx.Client(base_url=base, timeout=30) as client:
            _request(client, "GET", "/health")
            board_id = prepare_demo(client)
    except httpx.HTTPError:
        sys.exit(
            "예제 준비 실패: API 실행, KANBAN_API_URL, /docs 및 서버 로그를 확인하세요."
        )
    sys.stdout.write(
        f"예제 준비 완료 (기존 데이터 유지)\n"
        f"NEXT_PUBLIC_API_BASE_URL={base}\n"
        f"NEXT_PUBLIC_KANBAN_BOARD_ID={board_id}\n"
    )


if __name__ == "__main__":
    main()
