"""Board view schema (stages with their cards)."""

from pydantic import BaseModel

from app.schemas.board import BoardOut
from app.schemas.card import CardOut


class StageColumn(BaseModel):
    """One column of the board view."""

    id: int
    name: str
    position: int
    cards: list[CardOut]


class BoardView(BaseModel):
    """The whole board: columns in stage order, cards in card order."""

    board: BoardOut
    stages: list[StageColumn]
