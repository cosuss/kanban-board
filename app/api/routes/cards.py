"""Card routes."""

from typing import Annotated

from fastapi import APIRouter, Query, Response, status

from app.db.session import DbSession
from app.schemas.card import CardCreate, CardMove, CardOut, CardUpdate
from app.services import cards

router = APIRouter(tags=["cards"])


@router.get("/boards/{board_id}/cards")
def list_cards(
    board_id: int,
    db: DbSession,
    stage: str | None = None,
    assignee: str | None = None,
    milestone: str | None = None,
    q: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[CardOut]:
    """List a board's cards; filter by stage, assignee, milestone, or text (q)."""
    found = cards.list_cards(
        db,
        board_id,
        stage=stage,
        assignee=assignee,
        milestone=milestone,
        q=q,
        limit=limit,
        offset=offset,
    )
    return [cards.to_out(c) for c in found]


@router.post("/boards/{board_id}/cards", status_code=status.HTTP_201_CREATED)
def create_card(board_id: int, data: CardCreate, db: DbSession) -> CardOut:
    """Create a card. Names or ids both work for stage, assignee, and milestone."""
    return cards.to_out(cards.create_card(db, board_id, data))


@router.get("/cards/{card_id}")
def get_card(card_id: int, db: DbSession) -> CardOut:
    """Get one card."""
    return cards.to_out(cards.get_card(db, card_id))


@router.patch("/cards/{card_id}")
def update_card(card_id: int, data: CardUpdate, db: DbSession) -> CardOut:
    """Update a card. Send null for assignee_id or milestone_id to clear them."""
    return cards.to_out(cards.update_card(db, card_id, data))


@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_card(card_id: int, db: DbSession) -> Response:
    """Delete a card and its comments."""
    cards.delete_card(db, card_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/cards/{card_id}/move")
def move_card(card_id: int, data: CardMove, db: DbSession) -> CardOut:
    """Move a card to a stage (by name or id), optionally at a position."""
    return cards.to_out(cards.move_card(db, card_id, data))
