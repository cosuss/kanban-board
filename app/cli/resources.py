"""Commands for boards, members, stages, and milestones."""

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
    parse_day,
    say,
    say_deleted,
    show_table,
)

board_app = make_group(
    "board",
    "Create and manage boards.",
    [
        'kanban board add "Team A"',
        "kanban board list",
        "kanban board show 1",
        "kanban board delete 2",
    ],
)
member_app = make_group(
    "member",
    "Manage the people on the board.",
    [
        'kanban member add codex --name "Codex Agent" --role "AI agent"',
        "kanban member list",
    ],
)
stage_app = make_group(
    "stage",
    "Manage the columns of the board.",
    ["kanban stage list", 'kanban stage add "Review" --position 3'],
)
milestone_app = make_group(
    "milestone",
    "Manage goals (milestones) with optional due dates.",
    ['kanban milestone add "MVP" --due-on 2026-11-01', "kanban milestone list"],
)


# ---------------------------------------------------------------- board


@command(board_app, "list")
def board_list(ctx: typer.Context) -> None:
    """Show all boards."""
    show_table(
        ctx,
        request(ctx, "GET", "/boards"),
        [
            ("ID", "id"),
            ("NAME", "name"),
            ("REPO", "repo_url"),
        ],
        "No boards yet. Create one with: kanban board add NAME",
    )


@command(board_app, "add")
def board_add(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="The name of the board.")],
    repo_url: Annotated[
        str | None, typer.Option(help="The GitHub repository web address.")
    ] = None,
    *,
    no_default_stages: Annotated[
        bool,
        typer.Option(help="Do not create the Todo, In Progress and Done columns."),
    ] = False,
) -> None:
    """Create a new board. It starts with three columns: Todo, In Progress, and Done."""
    body = {
        "name": name,
        "repo_url": repo_url,
        "with_default_stages": not no_default_stages,
    }
    data = request(ctx, "POST", "/boards", body=body)
    say(ctx, data, f"Created board {data['id']}: {data['name']}")


@command(board_app, "show")
def board_show(
    ctx: typer.Context,
    board_id: Annotated[
        int | None,
        typer.Argument(min=1, help="The board number. Default: the --board value."),
    ] = None,
) -> None:
    """Show one board."""
    target = board_id or ctx.obj["board"]
    data = request(ctx, "GET", f"/boards/{target}")
    say(
        ctx, data, f"Board {data['id']}: {data['name']}\nRepo: {dash(data['repo_url'])}"
    )


@command(board_app, "update")
def board_update(
    ctx: typer.Context,
    board_id: Annotated[int, typer.Argument(min=1, help="The board number.")],
    name: Annotated[str | None, typer.Option(help="The new name.")] = None,
    repo_url: Annotated[
        str | None, typer.Option(help="The new GitHub repository web address.")
    ] = None,
    *,
    clear_repo_url: Annotated[
        bool, typer.Option(help="Remove the repository address.")
    ] = False,
) -> None:
    """Change only the details you provide. Anything you leave out stays as it is."""
    exclusive(repo_url=repo_url, clear_repo_url=clear_repo_url)
    body: dict = {}
    if name is not None:
        body["name"] = name
    if repo_url is not None:
        body["repo_url"] = repo_url
    if clear_repo_url:
        body["repo_url"] = None
    need_change(changed=bool(body))
    data = request(ctx, "PATCH", f"/boards/{board_id}", body=body)
    say(ctx, data, f"Updated board {data['id']}.")


@command(board_app, "delete")
def board_delete(
    ctx: typer.Context,
    board_id: Annotated[int, typer.Argument(min=1, help="The board number.")],
) -> None:
    """Delete a board with everything in it. This cannot be undone.

    The cards, people, columns and goals of the board are deleted too.
    """
    request(ctx, "DELETE", f"/boards/{board_id}")
    say_deleted(ctx, f"Deleted board {board_id} and everything in it.")


# --------------------------------------------------------------- member


@command(member_app, "list")
def member_list(ctx: typer.Context) -> None:
    """Show the people on the board."""
    show_table(
        ctx,
        request(ctx, "GET", board_path(ctx, "/members")),
        [
            ("ID", "id"),
            ("LOGIN", "github_login"),
            ("NAME", "name"),
            ("ROLE", "role"),
        ],
        "No members yet. Add one with: kanban member add GITHUB_LOGIN --name NAME",
    )


@command(member_app, "add")
def member_add(
    ctx: typer.Context,
    github_login: Annotated[str, typer.Argument(help="Their GitHub login name.")],
    name: Annotated[str, typer.Option(help="Their display name (required).")],
    role: Annotated[
        str | None, typer.Option(help="Their role, for example dev.")
    ] = None,
) -> None:
    """Add a person to the board. Use their GitHub login name."""
    body = {"github_login": github_login, "name": name, "role": role}
    data = request(ctx, "POST", board_path(ctx, "/members"), body=body)
    say(ctx, data, f"Added member {data['github_login']} (id {data['id']}).")


@command(member_app, "show")
def member_show(
    ctx: typer.Context,
    member_id: Annotated[int, typer.Argument(min=1, help="The member number.")],
) -> None:
    """Show one person."""
    data = request(ctx, "GET", f"/members/{member_id}")
    say(
        ctx,
        data,
        f"Member {data['id']}: {data['name']} ({data['github_login']})\n"
        f"Role: {dash(data['role'])}",
    )


@command(member_app, "update")
def member_update(
    ctx: typer.Context,
    member_id: Annotated[int, typer.Argument(min=1, help="The member number.")],
    github_login: Annotated[
        str | None, typer.Option(help="The new GitHub login.")
    ] = None,
    name: Annotated[str | None, typer.Option(help="The new display name.")] = None,
    role: Annotated[str | None, typer.Option(help="The new role.")] = None,
    *,
    clear_role: Annotated[bool, typer.Option(help="Remove the role.")] = False,
) -> None:
    """Change only the details you provide. Anything you leave out stays as it is."""
    exclusive(role=role, clear_role=clear_role)
    given = {"github_login": github_login, "name": name, "role": role}
    body: dict = {key: value for key, value in given.items() if value is not None}
    if clear_role:
        body["role"] = None
    need_change(changed=bool(body))
    data = request(ctx, "PATCH", f"/members/{member_id}", body=body)
    say(ctx, data, f"Updated member {data['id']}.")


@command(member_app, "delete")
def member_delete(
    ctx: typer.Context,
    member_id: Annotated[int, typer.Argument(min=1, help="The member number.")],
) -> None:
    """Remove a person. Their cards stay, but become unassigned."""
    request(ctx, "DELETE", f"/members/{member_id}")
    say_deleted(ctx, f"Deleted member {member_id}.")


# ---------------------------------------------------------------- stage


@command(stage_app, "list")
def stage_list(ctx: typer.Context) -> None:
    """Show the columns of the board, in order."""
    show_table(
        ctx,
        request(ctx, "GET", board_path(ctx, "/stages")),
        [
            ("ID", "id"),
            ("POSITION", "position"),
            ("NAME", "name"),
        ],
        "No stages yet. Add one with: kanban stage add NAME",
    )


@command(stage_app, "add")
def stage_add(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="The name of the column.")],
    position: Annotated[
        int | None,
        typer.Option(min=1, help="Where the column goes (1 is first). Default: last."),
    ] = None,
) -> None:
    """Add a column to the board."""
    data = request(
        ctx,
        "POST",
        board_path(ctx, "/stages"),
        body={"name": name, "position": position},
    )
    say(
        ctx,
        data,
        f'Added stage "{data["name"]}" (id {data["id"]}, position {data["position"]}).',
    )


@command(stage_app, "show")
def stage_show(
    ctx: typer.Context,
    stage_id: Annotated[int, typer.Argument(min=1, help="The stage number.")],
) -> None:
    """Show one column."""
    data = request(ctx, "GET", f"/stages/{stage_id}")
    say(ctx, data, f"Stage {data['id']}: {data['name']} (position {data['position']})")


@command(stage_app, "update")
def stage_update(
    ctx: typer.Context,
    stage_id: Annotated[int, typer.Argument(min=1, help="The stage number.")],
    name: Annotated[str | None, typer.Option(help="The new name.")] = None,
    position: Annotated[
        int | None, typer.Option(min=1, help="The new place (1 is first).")
    ] = None,
) -> None:
    """Change only the details you provide. Anything you leave out stays as it is."""
    body: dict = {}
    if name is not None:
        body["name"] = name
    if position is not None:
        body["position"] = position
    need_change(changed=bool(body))
    data = request(ctx, "PATCH", f"/stages/{stage_id}", body=body)
    say(ctx, data, f"Updated stage {data['id']}.")


@command(stage_app, "delete")
def stage_delete(
    ctx: typer.Context,
    stage_id: Annotated[int, typer.Argument(min=1, help="The stage number.")],
) -> None:
    """Delete an empty column. A column that still has cards cannot be deleted."""
    request(ctx, "DELETE", f"/stages/{stage_id}")
    say_deleted(ctx, f"Deleted stage {stage_id}.")


# ------------------------------------------------------------ milestone


@command(milestone_app, "list")
def milestone_list(ctx: typer.Context) -> None:
    """Show the goals (milestones) of the board."""
    show_table(
        ctx,
        request(ctx, "GET", board_path(ctx, "/milestones")),
        [
            ("ID", "id"),
            ("TITLE", "title"),
            ("DUE", "due_on"),
        ],
        "No milestones yet. Add one with: kanban milestone add TITLE",
    )


@command(milestone_app, "add")
def milestone_add(
    ctx: typer.Context,
    title: Annotated[str, typer.Argument(help="The name of the goal.")],
    due_on: Annotated[
        str | None, typer.Option(help="The due day, written as YYYY-MM-DD.")
    ] = None,
) -> None:
    """Add a goal with an optional due date."""
    body = {"title": title, "due_on": parse_day(due_on) if due_on else None}
    data = request(ctx, "POST", board_path(ctx, "/milestones"), body=body)
    say(ctx, data, f'Added milestone "{data["title"]}" (id {data["id"]}).')


@command(milestone_app, "show")
def milestone_show(
    ctx: typer.Context,
    milestone_id: Annotated[int, typer.Argument(min=1, help="The milestone number.")],
) -> None:
    """Show one goal."""
    data = request(ctx, "GET", f"/milestones/{milestone_id}")
    say(
        ctx,
        data,
        f"Milestone {data['id']}: {data['title']}\nDue: {dash(data['due_on'])}",
    )


@command(milestone_app, "update")
def milestone_update(
    ctx: typer.Context,
    milestone_id: Annotated[int, typer.Argument(min=1, help="The milestone number.")],
    title: Annotated[str | None, typer.Option(help="The new name.")] = None,
    due_on: Annotated[
        str | None, typer.Option(help="The new due day, written as YYYY-MM-DD.")
    ] = None,
    *,
    clear_due_on: Annotated[bool, typer.Option(help="Remove the due day.")] = False,
) -> None:
    """Change only the details you provide. Anything you leave out stays as it is."""
    exclusive(due_on=due_on, clear_due_on=clear_due_on)
    body: dict = {}
    if title is not None:
        body["title"] = title
    if due_on is not None:
        body["due_on"] = parse_day(due_on)
    if clear_due_on:
        body["due_on"] = None
    need_change(changed=bool(body))
    data = request(ctx, "PATCH", f"/milestones/{milestone_id}", body=body)
    say(ctx, data, f"Updated milestone {data['id']}.")


@command(milestone_app, "delete")
def milestone_delete(
    ctx: typer.Context,
    milestone_id: Annotated[int, typer.Argument(min=1, help="The milestone number.")],
) -> None:
    """Delete a goal. Its cards stay, but no longer belong to a goal."""
    request(ctx, "DELETE", f"/milestones/{milestone_id}")
    say_deleted(ctx, f"Deleted milestone {milestone_id}.")
