"""Commands for cards and comments."""

from typing import Annotated

import typer

from app.cli.client import request
from app.cli.common import (
    board_path,
    command,
    dash,
    exclusive,
    make_group,
    need_change,
    say,
    say_deleted,
    show_table,
    when,
)

card_app = make_group(
    "card",
    "Create, find, change, move and delete cards.",
    [
        'kanban card add "Write the login API" --stage "In Progress" --assignee codex',
        'kanban card list --stage "In Progress"',
        "kanban card move 12 Done",
        "kanban card show 12",
    ],
)
comment_app = make_group(
    "comment",
    "Read and write comments on cards.",
    [
        'kanban comment add 12 "Finished and tested." --author codex',
        "kanban comment list 12",
    ],
)

CARD_ID = Annotated[int, typer.Argument(min=1, help="The card number (its id).")]
COMMENT_ID = Annotated[int, typer.Argument(min=1, help="The comment number.")]
STAGE_HELP = 'The name of the column, for example "In Progress".'
ASSIGNEE_HELP = "The GitHub login of the person responsible, for example codex."
MILESTONE_HELP = "The title of the goal this card belongs to."


@command(card_app, "list")
def card_list(
    ctx: typer.Context,
    stage: Annotated[str | None, typer.Option(help=STAGE_HELP)] = None,
    assignee: Annotated[str | None, typer.Option(help=ASSIGNEE_HELP)] = None,
    milestone: Annotated[str | None, typer.Option(help=MILESTONE_HELP)] = None,
    query: Annotated[
        str | None,
        typer.Option(
            "--query",
            "--search",
            "-q",
            help="Show cards whose title or text contains these words.",
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(min=1, max=200, help="The most cards to show at once (1-200)."),
    ] = 50,
    offset: Annotated[
        int, typer.Option(min=0, help="How many cards to skip before showing results.")
    ] = 0,
) -> None:
    """Show cards.

    You can narrow the list by column, person, goal, or words in the title or text.
    """
    params = {
        "stage": stage,
        "assignee": assignee,
        "milestone": milestone,
        "q": query,
        "limit": limit,
        "offset": offset,
    }
    data = request(ctx, "GET", board_path(ctx, "/cards"), params=params)
    show_table(
        ctx,
        data,
        [
            ("ID", "id"),
            ("ISSUE", lambda r: f"#{r['issue_number']}"),
            ("STAGE", "stage"),
            ("ASSIGNEE", "assignee"),
            ("TITLE", "title"),
        ],
        "No cards found.",
    )
    if not ctx.obj["json"] and data:
        typer.echo(f"Showing {len(data)} card{'' if len(data) == 1 else 's'}.")


@command(card_app, "add")
def card_add(
    ctx: typer.Context,
    title: Annotated[str, typer.Argument(help="A short name for the card.")],
    body: Annotated[
        str | None, typer.Option(help="More details about the card.")
    ] = None,
    stage: Annotated[str | None, typer.Option(help=STAGE_HELP)] = None,
    stage_id: Annotated[
        int | None, typer.Option(min=1, help="The column number.")
    ] = None,
    assignee: Annotated[str | None, typer.Option(help=ASSIGNEE_HELP)] = None,
    assignee_id: Annotated[
        int | None, typer.Option(min=1, help="The person's number (member id).")
    ] = None,
    milestone: Annotated[str | None, typer.Option(help=MILESTONE_HELP)] = None,
    milestone_id: Annotated[
        int | None, typer.Option(min=1, help="The goal's number (milestone id).")
    ] = None,
    issue_number: Annotated[
        int | None,
        typer.Option(
            min=1, help="The GitHub issue number. Default: the next free one."
        ),
    ] = None,
) -> None:
    """Create a card. If you do not choose a column, it goes into the first column.

    You can name the column, person and goal (--stage, --assignee, --milestone)
    or give their numbers (--stage-id, --assignee-id, --milestone-id).
    """
    exclusive(stage=stage, stage_id=stage_id)
    exclusive(assignee=assignee, assignee_id=assignee_id)
    exclusive(milestone=milestone, milestone_id=milestone_id)
    payload = {
        "title": title,
        "body": body,
        "stage": stage,
        "stage_id": stage_id,
        "assignee": assignee,
        "assignee_id": assignee_id,
        "milestone": milestone,
        "milestone_id": milestone_id,
        "issue_number": issue_number,
    }
    data = request(ctx, "POST", board_path(ctx, "/cards"), body=payload)
    say(
        ctx,
        data,
        f"Created card {data['id']} (issue #{data['issue_number']}) "
        f"in {data['stage']}: {data['title']}",
    )


@command(card_app, "show")
def card_show(ctx: typer.Context, card_id: CARD_ID) -> None:
    """Show one card with all its details."""
    data = request(ctx, "GET", f"/cards/{card_id}")
    person = dash(data["assignee"])
    if data["assignee"] and data["assignee_name"]:
        person = f"{data['assignee']} ({data['assignee_name']})"
    say(
        ctx,
        data,
        f"Card {data['id']} (issue #{data['issue_number']}): {data['title']}\n"
        f"Stage:     {data['stage']}\n"
        f"Assignee:  {person}\n"
        f"Milestone: {dash(data['milestone'])}\n"
        f"Created:   {when(data['created_at'])}\n"
        f"Closed:    {when(data['closed_at'])}\n"
        f"Body:\n{data['body'] or '-'}",
    )


@command(card_app, "update")
def card_update(
    ctx: typer.Context,
    card_id: CARD_ID,
    title: Annotated[str | None, typer.Option(help="The new title.")] = None,
    body: Annotated[str | None, typer.Option(help="The new details text.")] = None,
    stage: Annotated[str | None, typer.Option(help=STAGE_HELP)] = None,
    stage_id: Annotated[
        int | None, typer.Option(min=1, help="The column number.")
    ] = None,
    assignee: Annotated[str | None, typer.Option(help=ASSIGNEE_HELP)] = None,
    assignee_id: Annotated[
        int | None, typer.Option(min=1, help="The person's number (member id).")
    ] = None,
    milestone: Annotated[str | None, typer.Option(help=MILESTONE_HELP)] = None,
    milestone_id: Annotated[
        int | None, typer.Option(min=1, help="The goal's number (milestone id).")
    ] = None,
    *,
    clear_body: Annotated[bool, typer.Option(help="Remove the details text.")] = False,
    clear_assignee: Annotated[
        bool, typer.Option(help="Remove the person responsible.")
    ] = False,
    clear_milestone: Annotated[bool, typer.Option(help="Remove the goal.")] = False,
) -> None:
    """Change only the details you provide. Anything you leave out stays as it is."""
    exclusive(stage=stage, stage_id=stage_id)
    exclusive(assignee=assignee, assignee_id=assignee_id, clear_assignee=clear_assignee)
    exclusive(
        milestone=milestone, milestone_id=milestone_id, clear_milestone=clear_milestone
    )
    exclusive(body=body, clear_body=clear_body)
    payload: dict = {
        key: value
        for key, value in (
            ("title", title),
            ("body", body),
            ("stage", stage),
            ("stage_id", stage_id),
            ("assignee", assignee),
            ("assignee_id", assignee_id),
            ("milestone", milestone),
            ("milestone_id", milestone_id),
        )
        if value is not None
    }
    if clear_body:
        payload["body"] = None
    if clear_assignee:
        payload["assignee_id"] = None
    if clear_milestone:
        payload["milestone_id"] = None
    need_change(changed=bool(payload))
    data = request(ctx, "PATCH", f"/cards/{card_id}", body=payload)
    say(ctx, data, f"Updated card {data['id']}.")


@command(card_app, "move")
def card_move(
    ctx: typer.Context,
    card_id: CARD_ID,
    stage: Annotated[
        str | None, typer.Argument(help='The name of the column, for example "Done".')
    ] = None,
    stage_id: Annotated[
        int | None, typer.Option(min=1, help="The column number, instead of its name.")
    ] = None,
    position: Annotated[
        int | None,
        typer.Option(
            min=1, help="Place in the column (1 is top). Default: the bottom."
        ),
    ] = None,
) -> None:
    """Move a card to another column. Moving a card to the last column closes it."""
    if (stage is None) == (stage_id is None):
        msg = "Give the column name or --stage-id (exactly one of them)."
        raise typer.BadParameter(msg)
    payload = {"stage": stage, "stage_id": stage_id, "position": position}
    data = request(ctx, "POST", f"/cards/{card_id}/move", body=payload)
    say(ctx, data, f"Moved card {data['id']} to {data['stage']}.")


@command(card_app, "delete")
def card_delete(ctx: typer.Context, card_id: CARD_ID) -> None:
    """Delete a card and its comments permanently. This cannot be undone."""
    request(ctx, "DELETE", f"/cards/{card_id}")
    say_deleted(ctx, f"Deleted card {card_id}.")


@command(comment_app, "list")
def comment_list(ctx: typer.Context, card_id: CARD_ID) -> None:
    """Show the comments on a card, oldest first."""
    data = request(ctx, "GET", f"/cards/{card_id}/comments")
    if ctx.obj["json"]:
        say(ctx, data, "")
        return
    if not data:
        typer.echo("No comments yet.")
    for item in data:
        typer.echo(
            f"[id {item['id']}] {when(item['created_at'])} "
            f"{dash(item['author'])}: {item['body']}"
        )


@command(comment_app, "add")
def comment_add(
    ctx: typer.Context,
    card_id: CARD_ID,
    body: Annotated[str, typer.Argument(help="The comment text.")],
    author: Annotated[
        str | None, typer.Option(help="The GitHub login of the person writing.")
    ] = None,
    author_id: Annotated[
        int | None, typer.Option(min=1, help="The writer's number (member id).")
    ] = None,
) -> None:
    """Add a comment to a card."""
    exclusive(author=author, author_id=author_id)
    payload = {"body": body, "author": author, "author_id": author_id}
    data = request(ctx, "POST", f"/cards/{card_id}/comments", body=payload)
    say(ctx, data, f"Added comment {data['id']} to card {data['card_id']}.")


@command(comment_app, "show")
def comment_show(ctx: typer.Context, comment_id: COMMENT_ID) -> None:
    """Show one comment."""
    data = request(ctx, "GET", f"/comments/{comment_id}")
    say(
        ctx,
        data,
        f"Comment {data['id']} on card {data['card_id']} by {dash(data['author'])} "
        f"({when(data['created_at'])})\n{data['body']}",
    )


@command(comment_app, "delete")
def comment_delete(ctx: typer.Context, comment_id: COMMENT_ID) -> None:
    """Delete a comment permanently."""
    request(ctx, "DELETE", f"/comments/{comment_id}")
    say_deleted(ctx, f"Deleted comment {comment_id}.")
