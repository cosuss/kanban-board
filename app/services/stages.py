"""Stage rules."""

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.models import Card, Stage
from app.schemas.stage import StageCreate, StageUpdate
from app.services.boards import get_board
from app.services.common import commit_or_conflict, get_or_404

_DUPLICATE = "a stage with this name or position already exists on the board"


def list_stages(db: Session, board_id: int) -> list[Stage]:
    """Return a board's stages in position order."""
    get_board(db, board_id)
    return list(
        db.scalars(
            select(Stage).where(Stage.board_id == board_id).order_by(Stage.position)
        )
    )


def get_stage(db: Session, stage_id: int) -> Stage:
    """Return one stage or raise 404."""
    return get_or_404(db, Stage, stage_id, "stage")


def create_stage(db: Session, board_id: int, data: StageCreate) -> Stage:
    """Create a stage; without a position it goes to the end.

    Returns:
        The new stage.

    """
    get_board(db, board_id)
    position = data.position
    if position is None:
        last = db.scalar(
            select(func.max(Stage.position)).where(Stage.board_id == board_id)
        )
        position = (last or 0) + 1
    stage = Stage(board_id=board_id, name=data.name, position=position)
    db.add(stage)
    commit_or_conflict(db, _DUPLICATE)
    return stage


def update_stage(db: Session, stage_id: int, data: StageUpdate) -> Stage:
    """Apply a partial update.

    Returns:
        The updated stage.

    """
    stage = get_stage(db, stage_id)
    if data.name is not None:
        stage.name = data.name
    if data.position is not None:
        stage.position = data.position
    commit_or_conflict(db, _DUPLICATE)
    return stage


def delete_stage(db: Session, stage_id: int) -> None:
    """Delete an empty stage.

    Raises:
        ConflictError: If cards are still in the stage.

    """
    stage = get_stage(db, stage_id)
    count = db.scalar(select(func.count()).where(Card.stage_id == stage.id))
    if count:
        msg = f"stage {stage.id} still has {count} card(s); move or delete them first"
        raise ConflictError(msg)
    db.execute(delete(Stage).where(Stage.id == stage.id))
    db.commit()
