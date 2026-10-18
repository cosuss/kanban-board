"""Board view: stages in order with their cards."""

from sqlalchemy.orm import Session

from app.schemas.board import BoardOut
from app.schemas.view import BoardView, StageColumn
from app.services import cards as card_service
from app.services.boards import get_board
from app.services.stages import list_stages

_ALL = 1_000_000


def board_view(db: Session, board_id: int) -> BoardView:
    """Build the board screen: stages by position, cards by position.

    Returns:
        The board with one column per stage.

    """
    board = get_board(db, board_id)
    stages = list_stages(db, board_id)
    cards = card_service.list_cards(
        db,
        board_id,
        stage=None,
        assignee=None,
        milestone=None,
        q=None,
        limit=_ALL,
        offset=0,
    )
    return BoardView(
        board=BoardOut.model_validate(board),
        stages=[
            StageColumn(
                id=stage.id,
                name=stage.name,
                position=stage.position,
                cards=[
                    card_service.to_out(card)
                    for card in cards
                    if card.stage_id == stage.id
                ],
            )
            for stage in stages
        ],
    )
