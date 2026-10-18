"""Kanban schema v3 (assignment #5): 6 tables, 5 indexes, RLS, v_board view.

Every statement is idempotent (IF NOT EXISTS / OR REPLACE) so that this runs
safely on an empty local database and on the Supabase database that already
has these tables.

Revision ID: 0001_kanban_v3
Revises:
Create Date: 2026-10-19
"""

from alembic import op

revision = "0001_kanban_v3"
down_revision = None
branch_labels = None
depends_on = None

TABLES = ("boards", "members", "stages", "milestones", "cards", "comments")

UPGRADE_STATEMENTS = (
    """
    create table if not exists boards (
        id        bigint generated always as identity primary key,
        name      text not null,
        repo_url  text unique
    )
    """,
    """
    create table if not exists members (
        id            bigint generated always as identity primary key,
        board_id      bigint not null references boards(id) on delete cascade,
        github_login  text not null unique,
        name          text not null,
        role          text
    )
    """,
    """
    create table if not exists stages (
        id        bigint generated always as identity primary key,
        board_id  bigint not null references boards(id) on delete cascade,
        name      text not null,
        position  int not null,
        unique (board_id, name),
        unique (board_id, position)
    )
    """,
    """
    create table if not exists milestones (
        id        bigint generated always as identity primary key,
        board_id  bigint not null references boards(id) on delete cascade,
        title     text not null,
        due_on    date,
        unique (board_id, title)
    )
    """,
    """
    create table if not exists cards (
        id            bigint generated always as identity primary key,
        stage_id      bigint not null references stages(id) on delete restrict,
        assignee_id   bigint references members(id) on delete set null,
        milestone_id  bigint references milestones(id) on delete set null,
        issue_number  int not null unique,
        title         text not null,
        body          text,
        position      int not null,
        created_at    timestamptz not null,
        closed_at     timestamptz
    )
    """,
    """
    create table if not exists comments (
        id          bigint generated always as identity primary key,
        card_id     bigint not null references cards(id) on delete cascade,
        author_id   bigint references members(id) on delete set null,
        body        text not null,
        created_at  timestamptz not null
    )
    """,
    "create index if not exists idx_cards_stage_id on cards(stage_id)",
    "create index if not exists idx_cards_assignee_id on cards(assignee_id)",
    "create index if not exists idx_cards_milestone_id on cards(milestone_id)",
    "create index if not exists idx_comments_card_id on comments(card_id)",
    "create index if not exists idx_comments_author_id on comments(author_id)",
    *(f"alter table {table} enable row level security" for table in TABLES),
    """
    comment on table boards is
    '칸반 보드. 보드-GitHub 저장소는 1:1이라 repo_url을 같은 표에 둔다.'
    """,
    """
    comment on table members is
    '팀원. GitHub 로그인으로 식별하며 보드 하나에 소속된다.'
    """,
    """
    comment on table stages is
    '칸반의 세로 칸(Todo/In Progress/Done). 테이블 컬럼과 헷갈리지 않게 단계라 부른다.'
    """,
    """
    comment on table milestones is
    '마일스톤(목표). 마감일은 없을 수 있다.'
    """,
    """
    comment on table cards is
    '카드 = GitHub 이슈. 상태는 stage_id로 표현한다. 담당자·마일스톤은 없을 수 있다.'
    """,
    """
    comment on table comments is
    '카드에 달린 댓글.'
    """,
    """
    create or replace view v_board with (security_invoker = true) as
    select s.name as stage, k.issue_number, k.title,
           m.name as assignee, ms.title as milestone
    from cards k
    join stages s on s.id = k.stage_id
    left join members m on m.id = k.assignee_id
    left join milestones ms on ms.id = k.milestone_id
    order by s.position, k.position
    """,
)


def upgrade() -> None:
    """Create the kanban schema if it is not already there."""
    for statement in UPGRADE_STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    """Drop the view, then children before parents."""
    op.execute("drop view if exists v_board")
    for table in reversed(TABLES):
        op.execute(f"drop table if exists {table} cascade")
