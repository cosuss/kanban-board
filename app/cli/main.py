"""The ``kanban`` command-line tool. It talks to the kanban API over the network."""

from typing import Annotated

import typer

from app.cli import cards, resources, system
from app.cli.common import (
    API_URL_HELP,
    BOARD_HELP,
    DEFAULT_API_URL,
    DEFAULT_BOARD,
    JSON_HELP,
    normalize_api_url,
)

app = typer.Typer(
    name="kanban",
    help="Manage your team's kanban board from the command line.",
    epilog=(
        "Examples:\n\n"
        "  kanban db upgrade\n\n"
        "  kanban serve\n\n"
        '  kanban card add "Write the login API" --stage "In Progress"\n\n'
        "  kanban view\n\n"
        "Run kanban COMMAND --help to learn more about one command."
    ),
    no_args_is_help=True,
    add_completion=False,
)


def _check_api_url(value: str) -> str:
    return normalize_api_url(value)


@app.callback()
def main(
    ctx: typer.Context,
    api_url: Annotated[
        str,
        typer.Option(
            envvar="KANBAN_API_URL",
            metavar="URL",
            help=API_URL_HELP,
            callback=_check_api_url,
        ),
    ] = DEFAULT_API_URL,
    board: Annotated[
        int,
        typer.Option(min=1, envvar="KANBAN_BOARD", metavar="INT", help=BOARD_HELP),
    ] = DEFAULT_BOARD,
    *,
    as_json: Annotated[bool, typer.Option("--json", help=JSON_HELP)] = False,
) -> None:
    """Manage your team's kanban board from the command line."""
    ctx.obj = {"api_url": api_url, "board": board, "json": as_json}


system.register(app)
app.add_typer(system.db_app, name="db")
app.add_typer(resources.board_app, name="board")
app.add_typer(resources.member_app, name="member")
app.add_typer(resources.stage_app, name="stage")
app.add_typer(resources.milestone_app, name="milestone")
app.add_typer(cards.card_app, name="card")
app.add_typer(cards.comment_app, name="comment")
