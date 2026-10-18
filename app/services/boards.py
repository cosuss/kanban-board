"""Board rules: default stages and full deletion."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Board, Card, Stage
from app.schemas.board import BoardCreate, BoardUpdate
from app.services.common import commit_or_conflict, flush_or_conflict, get_or_404

DEFAULT_STAGES = ("Todo", "In Progress", "Done")
_DUPLICATE_REPO = "a board with this repo_url already exists"


def list_boards(db: Session) -> list[Board]:
    """Return all boards ordered by id."""
    return list(db.scalars(select(Board).order_by(Board.id)))


def get_board(db: Session, board_id: int) -> Board:
    """Return one board or raise 404."""
    return get_or_404(db, Board, board_id, "board")


def create_board(db: Session, data: BoardCreate) -> Board:
    """Create a board, with Todo / In Progress / Done unless told otherwise.

    Returns:
        The new board.

    """
    board = Board(name=data.name, repo_url=data.repo_url)
    db.add(board)
    flush_or_conflict(db, _DUPLICATE_REPO)
    if data.with_default_stages:
        db.add_all(
            Stage(board_id=board.id, name=name, position=index)
            for index, name in enumerate(DEFAULT_STAGES, start=1)
        )
    commit_or_conflict(db, _DUPLICATE_REPO)
    return board


def update_board(db: Session, board_id: int, data: BoardUpdate) -> Board:
    """Apply a partial update.

    Returns:
        The updated board.

    """
    board = get_board(db, board_id)
    if data.name is not None:
        board.name = data.name
    if "repo_url" in data.model_fields_set:
        board.repo_url = data.repo_url
    commit_or_conflict(db, _DUPLICATE_REPO)
    return board


def delete_board(db: Session, board_id: int) -> None:
    """Delete a board with its cards (cards.stage_id is RESTRICT, so go first)."""
    board = get_board(db, board_id)
    stage_ids = select(Stage.id).where(Stage.board_id == board.id)
    db.execute(delete(Card).where(Card.stage_id.in_(stage_ids)))
    db.execute(delete(Board).where(Board.id == board.id))
    db.commit()
