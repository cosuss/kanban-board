"""Load test for the kanban API (stdlib + httpx only).

Usage::

    DATABASE_URL=postgresql+psycopg://localhost/kanban_stress \
        uv run python scripts/stress_test.py all --url http://127.0.0.1:8002

Scenarios: seed, A (concurrent reads), B (concurrent creates), C (concurrent
moves), D (connection-pool pressure). B and C verify invariants straight in
the database, so ``DATABASE_URL`` must point at the database the server uses.
Never aim it at a real board: scenario B and C write hundreds of cards.
"""

# ruff: file-ignore[any-type, blocking-path-method-in-async-function, implicit-namespace-package, too-many-arguments, too-many-positional-arguments, line-too-long, undocumented-public-function, docstring-missing-returns]
# One-off CLI script: loose typing/docstrings are fine; it is not part of the app.
import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
import psycopg

API = "/api/v1"
TIMEOUT = httpx.Timeout(120.0)
_settings = {"timeout": 120.0}  # seconds; overridden by --timeout


def _out(text: str) -> None:
    sys.stdout.write(text + "\n")
    sys.stdout.flush()


def _pg_url() -> str:
    url = os.environ["DATABASE_URL"]
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def _pct(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, round(pct / 100 * (len(ordered) - 1)))
    return ordered[index]


async def _request(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    method: str,
    path: str,
    host: str,
    body: Any,
) -> int:
    """Send one keep-alive HTTP/1.1 request and return the status code."""
    data = b"" if body is None else json.dumps(body).encode()
    head = (
        f"{method} {path} HTTP/1.1\r\nHost: {host}\r\nAccept: application/json\r\n"
        f"Content-Type: application/json\r\nContent-Length: {len(data)}\r\n\r\n"
    )
    writer.write(head.encode() + data)
    await writer.drain()
    raw = await reader.readuntil(b"\r\n\r\n")
    lines = raw.decode("latin-1").split("\r\n")
    code = int(lines[0].split()[1])
    length = 0
    for line in lines[1:]:
        if line.lower().startswith("content-length:"):
            length = int(line.split(":", 1)[1])
    if length:
        await reader.readexactly(length)
    return code


async def _hammer(
    base: str,
    method: str,
    path: Any,
    total: int,
    concurrency: int,
    payload_for: Any = None,
) -> dict[str, Any]:
    """Send ``total`` requests with exactly ``concurrency`` keep-alive sockets.

    A tiny raw-asyncio HTTP client is used because httpx itself becomes the
    bottleneck at 100+ connections (it measured ~170 req/s against a server
    that answers 2,000+ req/s), which would hide the server's real numbers.
    """
    parts = urlsplit(base)
    host, port = parts.hostname or "127.0.0.1", parts.port or 80
    latencies: list[float] = []
    statuses: Counter[str] = Counter()
    queue: asyncio.Queue[int] = asyncio.Queue()
    for i in range(total):
        queue.put_nowait(i)

    async def worker() -> None:
        conn: tuple[asyncio.StreamReader, asyncio.StreamWriter] | None = None
        while True:
            try:
                i = queue.get_nowait()
            except asyncio.QueueEmpty:
                break
            url = path(i) if callable(path) else path
            body = payload_for(i) if payload_for else None
            start = time.perf_counter()
            try:
                if conn is None:
                    conn = await asyncio.open_connection(host, port)
                code = await asyncio.wait_for(
                    _request(*conn, method, url, f"{host}:{port}", body),
                    timeout=_settings["timeout"],
                )
                statuses[str(code)] += 1
            except (OSError, asyncio.IncompleteReadError, TimeoutError) as exc:
                statuses[type(exc).__name__] += 1
                if conn is not None:
                    conn[1].close()
                conn = None
            latencies.append((time.perf_counter() - start) * 1000)
        if conn is not None:
            conn[1].close()

    start_all = time.perf_counter()
    await asyncio.gather(*(worker() for _ in range(concurrency)))
    wall = time.perf_counter() - start_all
    ok = sum(n for code, n in statuses.items() if code.startswith(("2", "3")))
    return {
        "method": method,
        "concurrency": concurrency,
        "requests": total,
        "wall_s": round(wall, 2),
        "rps": round(total / wall, 1),
        "mean_ms": round(statistics.fmean(latencies), 1),
        "p50_ms": round(_pct(latencies, 50), 1),
        "p95_ms": round(_pct(latencies, 95), 1),
        "p99_ms": round(_pct(latencies, 99), 1),
        "max_ms": round(max(latencies), 1),
        "error_rate": round(1 - ok / total, 4),
        "statuses": dict(statuses),
    }


async def seed(base: str) -> int:
    """Create one board, 3 members and 200 cards; return the board id."""
    async with httpx.AsyncClient(base_url=base + API, timeout=TIMEOUT) as c:
        board = (await c.post("/boards", json={"name": "stress"})).json()
        bid = board["id"]
        for login in ("alice", "bob", "carol"):
            await c.post(
                f"/boards/{bid}/members", json={"github_login": login, "name": login}
            )
    logins = ("alice", "bob", "carol")
    res = await _hammer(
        base,
        "POST",
        f"{API}/boards/{bid}/cards",
        200,
        10,
        lambda i: {
            "title": f"seed {i}",
            "body": "seed body " * 5,
            "assignee": logins[i % 3],
        },
    )
    _out(f"seed board={bid} cards: {res['statuses']}")
    return bid


async def scenario_a(
    base: str, bid: int, concs: tuple[int, ...] = (50, 100, 200)
) -> list[dict[str, Any]]:
    rows = []
    for label, path in (
        ("view", f"{API}/boards/{bid}/view"),
        ("cards?limit=50", f"{API}/boards/{bid}/cards?limit=50"),
    ):
        for conc in concs:
            res = await _hammer(base, "GET", path, 1000, conc)
            res["endpoint"] = label
            rows.append(res)
            _out(json.dumps(res))
    return rows


def _query(sql: str, params: tuple = ()) -> list[tuple]:
    with psycopg.connect(_pg_url()) as conn:
        return conn.execute(sql, params).fetchall()


async def scenario_b(base: str, bid: int) -> dict[str, Any]:
    before = _query("select count(*) from cards")[0][0]
    res = await _hammer(
        base,
        "POST",
        f"{API}/boards/{bid}/cards",
        500,
        50,
        lambda i: {"title": f"concurrent {i}"},
    )
    dup_issue = _query(
        "select issue_number, count(*) from cards group by 1 having count(*) > 1"
    )
    dup_pos = _query(
        "select stage_id, position, count(*) from cards "
        "group by 1, 2 having count(*) > 1"
    )
    after = _query("select count(*) from cards")[0][0]
    res.update({
        "cards_added": after - before,
        "dup_issue_numbers": len(dup_issue),
        "dup_positions": len(dup_pos),
    })
    _out(json.dumps(res))
    return res


async def scenario_c(base: str, bid: int) -> dict[str, Any]:
    async with httpx.AsyncClient(base_url=base + API, timeout=TIMEOUT) as c:
        cards = (
            await c.get(f"/boards/{bid}/cards", params={"stage": "Todo", "limit": 100})
        ).json()
    ids = [card["id"] for card in cards]
    res = await _hammer(
        base,
        "POST",
        lambda i: f"{API}/cards/{ids[i]}/move",
        len(ids),
        len(ids),
        lambda _i: {"stage": "Done"},
    )
    dup_pos = _query(
        "select s.name, c.position, count(*) from cards c join stages s on s.id = c.stage_id "
        "group by 1, 2 having count(*) > 1"
    )
    missing_closed = _query(
        "select count(*) from cards c join stages s on s.id = c.stage_id "
        "where s.name = 'Done' and c.closed_at is null"
    )[0][0]
    wrong_closed = _query(
        "select count(*) from cards c join stages s on s.id = c.stage_id "
        "where s.name <> 'Done' and c.closed_at is not null"
    )[0][0]
    moved = _query(
        "select count(*) from cards c join stages s on s.id = c.stage_id "
        "where s.name = 'Done' and c.id = any(%s)",
        (ids,),
    )[0][0]
    res.update({
        "moved_in_done": moved,
        "dup_positions": len(dup_pos),
        "done_missing_closed_at": missing_closed,
        "non_done_with_closed_at": wrong_closed,
    })
    _out(json.dumps(res))
    return res


async def scenario_d(
    base: str, bid: int, label: str, concs: tuple[int, ...] = (100, 300)
) -> list[dict[str, Any]]:
    rows = []
    mixes = (
        ("view", "GET", f"{API}/boards/{bid}/view", None),
        ("cards?limit=50", "GET", f"{API}/boards/{bid}/cards?limit=50", None),
        ("health", "GET", "/health", None),
    )
    for name, method, path, payload in mixes:
        for conc in concs:
            res = await _hammer(base, method, path, max(1000, conc * 3), conc, payload)
            res.update({"endpoint": name, "pool": label})
            rows.append(res)
            _out(json.dumps(res))
    return rows


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=["seed", "A", "B", "C", "D", "all"])
    parser.add_argument("--url", default="http://127.0.0.1:8002")
    parser.add_argument("--board", type=int, default=1)
    parser.add_argument("--label", default="default", help="pool label for scenario D")
    parser.add_argument("--timeout", type=float, default=120.0, help="per request, s")
    parser.add_argument("--conc", help="comma list overriding concurrency for A/D")
    parser.add_argument("--json-out", help="write all results to this file")
    args = parser.parse_args()
    _settings["timeout"] = args.timeout
    results: dict[str, Any] = {}
    override = (tuple(int(x) for x in args.conc.split(",")),) if args.conc else ()
    conc_a = conc_d = override
    if args.scenario in {"seed", "all"}:
        args.board = await seed(args.url)
    if args.scenario in {"A", "all"}:
        results["A"] = await scenario_a(args.url, args.board, *conc_a)
    if args.scenario in {"B", "all"}:
        results["B"] = await scenario_b(args.url, args.board)
    if args.scenario in {"C", "all"}:
        results["C"] = await scenario_c(args.url, args.board)
    if args.scenario in {"D", "all"}:
        results["D"] = await scenario_d(args.url, args.board, args.label, *conc_d)
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
