"""Milestone rules."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Milestone
from app.schemas.milestone import MilestoneCreate, MilestoneUpdate
from app.services.boards import get_board
from app.services.common import commit_or_conflict, get_or_404

_DUPLICATE = "a milestone with this title already exists on the board"


def list_milestones(db: Session, board_id: int) -> list[Milestone]:
    """Return a board's milestones ordered by id."""
    get_board(db, board_id)
    return list(
        db.scalars(
            select(Milestone)
            .where(Milestone.board_id == board_id)
            .order_by(Milestone.id)
        )
    )


def get_milestone(db: Session, milestone_id: int) -> Milestone:
    """Return one milestone or raise 404."""
    return get_or_404(db, Milestone, milestone_id, "milestone")


def create_milestone(db: Session, board_id: int, data: MilestoneCreate) -> Milestone:
    """Create a milestone on a board.

    Returns:
        The new milestone.

    """
    get_board(db, board_id)
    milestone = Milestone(board_id=board_id, title=data.title, due_on=data.due_on)
    db.add(milestone)
    commit_or_conflict(db, _DUPLICATE)
    return milestone


def update_milestone(
    db: Session, milestone_id: int, data: MilestoneUpdate
) -> Milestone:
    """Apply a partial update (null due_on clears the date).

    Returns:
        The updated milestone.

    """
    milestone = get_milestone(db, milestone_id)
    if data.title is not None:
        milestone.title = data.title
    if "due_on" in data.model_fields_set:
        milestone.due_on = data.due_on
    commit_or_conflict(db, _DUPLICATE)
    return milestone


def delete_milestone(db: Session, milestone_id: int) -> None:
    """Delete a milestone; its cards just lose the milestone."""
    milestone = get_milestone(db, milestone_id)
    db.execute(delete(Milestone).where(Milestone.id == milestone.id))
    db.commit()
