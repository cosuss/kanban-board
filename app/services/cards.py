"""Card rules: issue numbers, positions, closed_at, and name resolution."""

from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, joinedload

from app.core.errors import ConflictError, InvalidRequestError, NotFoundError
from app.models import Card, Member, Milestone, Stage
from app.schemas.card import CardCreate, CardMove, CardOut, CardUpdate
from app.services.boards import get_board

_ADVISORY_LOCK_KEY = 7_001  # serializes issue_number / position assignment
_DUPLICATE_ISSUE = "a card with this issue_number already exists"


def to_out(card: Card) -> CardOut:
    """Flatten a card (with stage/assignee/milestone loaded) into CardOut."""
    return CardOut(
        id=card.id,
        board_id=card.stage.board_id,
        stage_id=card.stage_id,
        stage=card.stage.name,
        assignee_id=card.assignee_id,
        assignee=card.assignee.github_login if card.assignee else None,
        assignee_name=card.assignee.name if card.assignee else None,
        milestone_id=card.milestone_id,
        milestone=card.milestone.title if card.milestone else None,
        issue_number=card.issue_number,
        title=card.title,
        body=card.body,
        position=card.position,
        created_at=card.created_at,
        closed_at=card.closed_at,
    )


def _with_joins() -> tuple:
    return (
        joinedload(Card.stage),
        joinedload(Card.assignee),
        joinedload(Card.milestone),
    )


def get_card(db: Session, card_id: int) -> Card:
    """Return a card with its relations loaded, or raise 404.

    Raises:
        NotFoundError: If the card does not exist.

    """
    card = db.scalar(
        select(Card)
        .where(Card.id == card_id)
        .options(*_with_joins())
        .execution_options(populate_existing=True)
    )
    if card is None:
        msg = f"card {card_id} not found"
        raise NotFoundError(msg)
    return card


def list_cards(
    db: Session,
    board_id: int,
    *,
    stage: str | None,
    assignee: str | None,
    milestone: str | None,
    q: str | None,
    limit: int,
    offset: int,
) -> list[Card]:
    """Return a board's cards, filtered, in stage order then card order."""
    get_board(db, board_id)
    stmt = (
        select(Card)
        .join(Stage, Stage.id == Card.stage_id)
        .where(Stage.board_id == board_id)
        .options(*_with_joins())
        .order_by(Stage.position, Card.position, Card.id)
        .limit(limit)
        .offset(offset)
    )
    if stage is not None:
        stmt = stmt.where(Stage.name == stage)
    if assignee is not None:
        stmt = stmt.join(Member, Member.id == Card.assignee_id).where(
            Member.github_login == assignee
        )
    if milestone is not None:
        stmt = stmt.join(Milestone, Milestone.id == Card.milestone_id).where(
            Milestone.title == milestone
        )
    if q:
        stmt = stmt.where(
            Card.title.icontains(q, autoescape=True)
            | Card.body.icontains(q, autoescape=True)
        )
    return list(db.scalars(stmt))


def _lock(db: Session) -> None:
    db.execute(select(func.pg_advisory_xact_lock(_ADVISORY_LOCK_KEY)))


def _resolve_stage(
    db: Session, board_id: int, name: str | None, stage_id: int | None
) -> Stage:
    if name is not None:
        stage = db.scalar(
            select(Stage).where(Stage.board_id == board_id, Stage.name == name)
        )
    else:
        stage = db.scalar(
            select(Stage).where(Stage.board_id == board_id, Stage.id == stage_id)
        )
    if stage is None:
        msg = f"stage {name if name is not None else stage_id!r} not found on board"
        raise NotFoundError(msg)
    return stage


def _resolve_member(
    db: Session, board_id: int, login: str | None, member_id: int | None
) -> Member:
    stmt = select(Member).where(Member.board_id == board_id)
    stmt = (
        stmt.where(Member.github_login == login)
        if login is not None
        else stmt.where(Member.id == member_id)
    )
    member = db.scalar(stmt)
    if member is None:
        msg = f"member {login if login is not None else member_id!r} not found on board"
        raise NotFoundError(msg)
    return member


def _resolve_milestone(
    db: Session, board_id: int, title: str | None, milestone_id: int | None
) -> Milestone:
    stmt = select(Milestone).where(Milestone.board_id == board_id)
    stmt = (
        stmt.where(Milestone.title == title)
        if title is not None
        else stmt.where(Milestone.id == milestone_id)
    )
    milestone = db.scalar(stmt)
    if milestone is None:
        msg = (
            f"milestone {title if title is not None else milestone_id!r} "
            "not found on board"
        )
        raise NotFoundError(msg)
    return milestone


def _is_last_stage(db: Session, stage: Stage) -> bool:
    last = db.scalar(
        select(func.max(Stage.position)).where(Stage.board_id == stage.board_id)
    )
    return stage.position == last


def _next_position(db: Session, stage_id: int, *, exclude_card: int = 0) -> int:
    last = db.scalar(
        select(func.max(Card.position)).where(
            Card.stage_id == stage_id, Card.id != exclude_card
        )
    )
    return (last or 0) + 1


def create_card(db: Session, board_id: int, data: CardCreate) -> Card:
    """Create a card with automatic issue_number, position, and closed_at.

    Returns:
        The new card.

    Raises:
        ConflictError: If the requested issue_number is already used.

    """
    get_board(db, board_id)
    if data.stage is not None or data.stage_id is not None:
        stage = _resolve_stage(db, board_id, data.stage, data.stage_id)
    else:
        stage = db.scalar(
            select(Stage)
            .where(Stage.board_id == board_id)
            .order_by(Stage.position)
            .limit(1)
        )
        if stage is None:
            msg = "board has no stages; create a stage first"
            raise InvalidRequestError(msg)
    assignee = (
        _resolve_member(db, board_id, data.assignee, data.assignee_id)
        if data.assignee is not None or data.assignee_id is not None
        else None
    )
    milestone = (
        _resolve_milestone(db, board_id, data.milestone, data.milestone_id)
        if data.milestone is not None or data.milestone_id is not None
        else None
    )
    _lock(db)
    if data.issue_number is None:
        issue_number = (db.scalar(select(func.max(Card.issue_number))) or 0) + 1
    else:
        issue_number = data.issue_number
        if db.scalar(select(Card.id).where(Card.issue_number == issue_number)):
            raise ConflictError(_DUPLICATE_ISSUE)
    now = datetime.now(UTC)
    card = Card(
        stage_id=stage.id,
        assignee_id=assignee.id if assignee else None,
        milestone_id=milestone.id if milestone else None,
        issue_number=issue_number,
        title=data.title,
        body=data.body,
        position=_next_position(db, stage.id),
        created_at=now,
        closed_at=now if _is_last_stage(db, stage) else None,
    )
    db.add(card)
    db.commit()
    return get_card(db, card.id)


def _apply_move(db: Session, card: Card, stage: Stage, position: int | None) -> None:
    if position is None:
        new_position = _next_position(db, stage.id, exclude_card=card.id)
    else:
        db.execute(
            update(Card)
            .where(
                Card.stage_id == stage.id,
                Card.position >= position,
                Card.id != card.id,
            )
            .values(position=Card.position + 1)
        )
        new_position = position
    if _is_last_stage(db, stage):
        card.closed_at = card.closed_at or datetime.now(UTC)
    else:
        card.closed_at = None
    card.stage_id = stage.id
    card.position = new_position


def move_card(db: Session, card_id: int, data: CardMove) -> Card:
    """Move a card to another stage (by name or id), keeping closed_at in sync.

    Returns:
        The moved card.

    """
    card = get_card(db, card_id)
    stage = _resolve_stage(db, card.stage.board_id, data.stage, data.stage_id)
    _lock(db)
    _apply_move(db, card, stage, data.position)
    db.commit()
    return get_card(db, card_id)


def update_card(db: Session, card_id: int, data: CardUpdate) -> Card:
    """Apply a partial update, including stage changes and clearing references.

    Returns:
        The updated card.

    """
    card = get_card(db, card_id)
    board_id = card.stage.board_id
    fields = data.model_fields_set
    if data.title is not None:
        card.title = data.title
    if "body" in fields:
        card.body = data.body
    if "assignee" in fields or "assignee_id" in fields:
        if data.assignee is not None or data.assignee_id is not None:
            member = _resolve_member(db, board_id, data.assignee, data.assignee_id)
            card.assignee_id = member.id
        else:
            card.assignee_id = None
    if "milestone" in fields or "milestone_id" in fields:
        if data.milestone is not None or data.milestone_id is not None:
            milestone = _resolve_milestone(
                db, board_id, data.milestone, data.milestone_id
            )
            card.milestone_id = milestone.id
        else:
            card.milestone_id = None
    if data.stage is not None or data.stage_id is not None:
        stage = _resolve_stage(db, board_id, data.stage, data.stage_id)
        if stage.id != card.stage_id:
            _lock(db)
            _apply_move(db, card, stage, None)
    db.commit()
    return get_card(db, card_id)


def delete_card(db: Session, card_id: int) -> None:
    """Delete a card; its comments go with it."""
    card = get_card(db, card_id)
    db.delete(card)
    db.commit()
