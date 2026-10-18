"""Board routes."""

from fastapi import APIRouter, Response, status

from app.db.session import DbSession
from app.schemas.board import BoardCreate, BoardOut, BoardUpdate
from app.schemas.view import BoardView
from app.services import boards, view

router = APIRouter(prefix="/boards", tags=["boards"])


@router.get("")
def list_boards(db: DbSession) -> list[BoardOut]:
    """List all boards."""
    return [BoardOut.model_validate(b) for b in boards.list_boards(db)]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_board(data: BoardCreate, db: DbSession) -> BoardOut:
    """Create a board (with Todo / In Progress / Done by default)."""
    return BoardOut.model_validate(boards.create_board(db, data))


@router.get("/{board_id}")
def get_board(board_id: int, db: DbSession) -> BoardOut:
    """Get one board."""
    return BoardOut.model_validate(boards.get_board(db, board_id))


@router.patch("/{board_id}")
def update_board(board_id: int, data: BoardUpdate, db: DbSession) -> BoardOut:
    """Update a board's name or repo_url."""
    return BoardOut.model_validate(boards.update_board(db, board_id, data))


@router.delete("/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_board(board_id: int, db: DbSession) -> Response:
    """Delete a board together with its cards."""
    boards.delete_board(db, board_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{board_id}/view")
def get_board_view(board_id: int, db: DbSession) -> BoardView:
    """Get the board screen: stages in order, each with its cards."""
    return view.board_view(db, board_id)
