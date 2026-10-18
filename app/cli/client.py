"""HTTP access to the kanban API: one client factory and one request function."""

import json
import sys
from typing import Any, NoReturn

import httpx
import typer

API_PREFIX = "/api/v1"
TIMEOUT_SECONDS = 10.0


def get_client(api_url: str) -> httpx.Client:
    """Create the HTTP client for one command run.

    Tests replace this function to talk to the app without a server.

    Returns:
        A client whose paths are relative to the API prefix.

    """
    return httpx.Client(base_url=api_url + API_PREFIX, timeout=TIMEOUT_SECONDS)


def fail(message: str) -> NoReturn:
    """Print one error line to stderr and stop with exit code 1.

    Raises:
        Exit: Always, with code 1.

    """
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(1)


def _detail(response: httpx.Response) -> str:
    """Pull a short message out of an error response.

    Returns:
        The server's detail text, or the status text when there is none.

    """
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        detail = None
    if isinstance(detail, list) and detail:
        first = detail[0]
        if isinstance(first, dict):
            where = ".".join(
                str(part) for part in first.get("loc", []) if part != "body"
            )
            message = str(first.get("msg", "invalid request"))
            return f"{where}: {message}" if where else message
    if isinstance(detail, str):
        return detail
    return response.text or response.reason_phrase


def _send(
    api_url: str, method: str, path: str, params: dict[str, Any], body: Any
) -> httpx.Response:
    client = get_client(api_url)
    try:
        return client.request(method, path, params=params, json=body)
    finally:
        client.close()


def request(
    ctx: typer.Context,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> Any:
    """Send one request and return the decoded JSON (None for an empty reply).

    Returns:
        The decoded response body, or None when the server sent no content.

    """
    api_url = ctx.obj["api_url"]
    query = {key: value for key, value in (params or {}).items() if value is not None}
    try:
        response = _send(api_url, method, path, query, body)
    except httpx.TimeoutException:
        fail("The server did not answer in time. Check that it is running.")
    except httpx.RequestError:
        fail(
            f"Cannot reach the kanban server at {api_url}. "
            'Start it with "kanban serve".'
        )
    if response.is_error:
        fail(f"{_detail(response)} ({response.status_code})")
    if response.status_code == httpx.codes.NO_CONTENT or not response.content:
        return None
    return response.json()


def print_json(data: Any) -> None:
    """Print a JSON value the way every command does."""
    sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
