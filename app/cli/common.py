"""Shared pieces for commands: global options, output helpers, formatting."""

import sys
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from operator import itemgetter
from typing import Any
from urllib.parse import urlsplit

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text
from typer.core import TyperCommand, TyperOption

from app.cli.client import print_json

DEFAULT_API_URL = "http://127.0.0.1:8000"
DEFAULT_BOARD = 1
NO_VALUE = "-"
WIDE_PIPE_WIDTH = 120

API_URL_HELP = "Use a different kanban server. Default: http://127.0.0.1:8000."
BOARD_HELP = "The board number to work on. Default: 1."
JSON_HELP = "Print the result as JSON for use with other tools."


def normalize_api_url(value: str) -> str:
    """Check a server address and drop a trailing slash.

    Returns:
        The address without a trailing slash.

    Raises:
        BadParameter: When the address is not a web address with a host.

    """
    address = value.strip().rstrip("/")
    parts = urlsplit(address)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        msg = "Use a server address such as http://127.0.0.1:8000."
        raise typer.BadParameter(msg)
    return address


def _set_api_url(_ctx: object, _param: object, value: str | None) -> None:
    if value is not None:
        _ctx.obj["api_url"] = normalize_api_url(value)


def _set_board(_ctx: object, _param: object, value: int | None) -> None:
    if value is None:
        return
    if value < 1:
        msg = "The board number must be 1 or more."
        raise typer.BadParameter(msg)
    _ctx.obj["board"] = value


def _set_json(_ctx: object, _param: object, value: object) -> None:
    if value:
        _ctx.obj["json"] = True


class GlobalOptionsCommand(TyperCommand):
    """A command that also accepts --api-url, --board and --json after its name."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Add the three global options to the command."""
        super().__init__(*args, **kwargs)
        self.params.extend([
            TyperOption(
                param_decls=["--api-url"],
                type=str,
                metavar="URL",
                help=API_URL_HELP,
                expose_value=False,
                callback=_set_api_url,
            ),
            TyperOption(
                param_decls=["--board"],
                type=int,
                metavar="INT",
                help=BOARD_HELP,
                expose_value=False,
                callback=_set_board,
            ),
            TyperOption(
                param_decls=["--json"],
                is_flag=True,
                help=JSON_HELP,
                expose_value=False,
                callback=_set_json,
            ),
        ])


def command(group: typer.Typer, name: str, **kwargs: Any) -> Callable[..., Any]:
    """Register a command that understands the global options.

    Returns:
        The decorator that registers the function.

    """
    return group.command(name, cls=GlobalOptionsCommand, **kwargs)


def make_group(name: str, help_text: str, examples: Sequence[str]) -> typer.Typer:
    """Create a command group with a help text and example lines.

    Returns:
        The new group.

    """
    epilog = "Examples:\n\n" + "\n\n".join(f"  {line}" for line in examples)
    return typer.Typer(
        name=name,
        help=help_text,
        epilog=epilog,
        no_args_is_help=True,
    )


def wants_json(ctx: typer.Context) -> bool:
    """Tell whether the user asked for JSON output.

    Returns:
        True when ``--json`` was given.

    """
    return bool(ctx.obj["json"])


def board_path(ctx: typer.Context, suffix: str = "") -> str:
    """Build a path under the selected board.

    Returns:
        ``/boards/<board><suffix>``.

    """
    return f"/boards/{ctx.obj['board']}{suffix}"


def say(ctx: typer.Context, data: Any, message: str) -> None:
    """Print the API data as JSON, or one sentence of text."""
    if wants_json(ctx):
        print_json(data)
    else:
        typer.echo(message)


def say_deleted(ctx: typer.Context, message: str) -> None:
    """Print the delete confirmation (nothing at all in JSON mode)."""
    if not wants_json(ctx):
        typer.echo(message)


def when(value: str | None) -> str:
    """Shorten an ISO timestamp to ``YYYY-MM-DD HH:MM`` in UTC.

    Returns:
        The short text, or ``-`` when there is no value.

    """
    if not value:
        return NO_VALUE
    return datetime.fromisoformat(value).astimezone(UTC).strftime("%Y-%m-%d %H:%M")


def dash(value: object) -> str:
    """Show a missing value as ``-``.

    Returns:
        The value as text.

    """
    return NO_VALUE if value is None or not str(value) else str(value)


def parse_day(value: str) -> str:
    """Check a YYYY-MM-DD day.

    Returns:
        The day in ISO format.

    Raises:
        BadParameter: When the text is not a valid day.

    """
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as error:
        msg = "Use a day written as YYYY-MM-DD."
        raise typer.BadParameter(msg) from error


def console() -> Console:
    """Make a rich console that writes to the current stdout.

    Returns:
        A console that is wide enough when output goes to a pipe.

    """
    return Console(
        file=sys.stdout,
        width=None if sys.stdout.isatty() else WIDE_PIPE_WIDTH,
        highlight=False,
    )


def show_table(
    ctx: typer.Context,
    data: list[dict[str, Any]],
    columns: Sequence[tuple[str, str | Callable[[dict[str, Any]], object]]],
    empty: str,
) -> None:
    """Print a list as JSON or as a table.

    Args:
        ctx: The command context.
        data: The API list.
        columns: Pairs of a header and the key (or function) that reads a cell.
        empty: The sentence to show when the list is empty.

    """
    if wants_json(ctx):
        print_json(data)
        return
    if not data:
        typer.echo(empty)
        return
    table = Table(show_edge=False, pad_edge=False)
    readers = [
        (header, itemgetter(read) if isinstance(read, str) else read)
        for header, read in columns
    ]
    for header, _ in readers:
        table.add_column(header, overflow="fold")
    for row in data:
        table.add_row(*(Text(dash(read(row))) for _, read in readers))
    console().print(table)


def need_change(*, changed: bool) -> None:
    """Stop with a usage error when an update has nothing to change.

    Raises:
        BadParameter: When no change option was given.

    """
    if not changed:
        msg = "Give at least one option to change. See --help."
        raise typer.BadParameter(msg)


def exclusive(**options: object) -> None:
    """Stop with a usage error when more than one of the given options is set.

    Raises:
        BadParameter: When two or more values are set.

    """
    given = [
        name
        for name, value in options.items()
        if value is not None and value is not False
    ]
    if len(given) > 1:
        names = " and ".join("--" + name.replace("_", "-") for name in given)
        msg = f"Use only one of these: {names}."
        raise typer.BadParameter(msg)
