"""Commands for the server itself: health, serve, db upgrade, and view."""

from pathlib import Path
from typing import Annotated

import typer
from rich.table import Table
from rich.text import Text

from app.cli.client import fail, print_json, request
from app.cli.common import (
    board_path,
    command,
    console,
    make_group,
    say,
    wants_json,
)

ROOT = Path(__file__).resolve().parents[2]

db_app = make_group(
    "db",
    "Prepare the database.",
    ["kanban db upgrade"],
)


def register(app: typer.Typer) -> None:
    """Add the system commands to the root app."""
    command(app, "health")(health)
    command(app, "serve")(serve)
    command(app, "view")(view)
    command(db_app, "upgrade")(db_upgrade)


def health(ctx: typer.Context) -> None:
    """Check that the server and its database are working."""
    data = request(ctx, "GET", "/health")
    say(ctx, data, f"Server is running. Database: {data['database']}.")


def serve(
    host: Annotated[
        str, typer.Option(help="The address to listen on. Default: 127.0.0.1.")
    ] = "127.0.0.1",
    port: Annotated[
        int, typer.Option(min=1, max=65535, help="The port to listen on.")
    ] = 8000,
    *,
    reload: Annotated[
        bool, typer.Option(help="Restart the server when the code changes.")
    ] = False,
) -> None:
    """Start the kanban server on this computer. Keep this window open while you work.

    The server needs the DATABASE_URL setting. Run "kanban db upgrade" once first.
    """
    import uvicorn

    typer.echo(f"Starting kanban server at http://{host}:{port} (press Ctrl+C to stop)")
    try:
        uvicorn.run("app.main:app", host=host, port=port, reload=reload)
    except OSError as error:
        message = f"Cannot start the server: {error}"
        fail(message)


def db_upgrade() -> None:
    """Set up or update the database tables. Safe to run more than once."""
    from alembic.config import Config

    from alembic import command as alembic_command

    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    try:
        alembic_command.upgrade(config, "head")
    except Exception as error:
        msg = "Cannot connect to the database. Check DATABASE_URL."
        raise fail(msg) from error
    typer.echo("Database is up to date.")


def _card_line(card: dict) -> str:
    return f"#{card['issue_number']} {card['title']} ({card['assignee'] or '-'})"


def view(ctx: typer.Context) -> None:
    """Show the whole board, one column per stage."""
    data = request(ctx, "GET", board_path(ctx, "/view"))
    if wants_json(ctx):
        print_json(data)
        return
    typer.echo(f"Board {data['board']['id']}: {data['board']['name']}")
    stages = data["stages"]
    if not stages:
        typer.echo("(no stages)")
        return
    table = Table(show_edge=False, pad_edge=False, expand=False)
    for stage in stages:
        table.add_column(f"{stage['name']} ({len(stage['cards'])})", overflow="fold")
    height = max(len(stage["cards"]) for stage in stages)
    for index in range(max(height, 1)):
        row = []
        for stage in stages:
            cards = stage["cards"]
            if index < len(cards):
                row.append(Text(_card_line(cards[index])))
            else:
                row.append(Text("(empty)" if not cards and index == 0 else ""))
        table.add_row(*row)
    console().print(table)
