"""Comment routes."""

from fastapi import APIRouter, Response, status

from app.db.session import DbSession
from app.schemas.comment import CommentCreate, CommentOut
from app.services import comments

router = APIRouter(tags=["comments"])


@router.get("/cards/{card_id}/comments")
def list_comments(card_id: int, db: DbSession) -> list[CommentOut]:
    """List a card's comments, oldest first."""
    return [comments.to_out(c) for c in comments.list_comments(db, card_id)]


@router.post("/cards/{card_id}/comments", status_code=status.HTTP_201_CREATED)
def create_comment(card_id: int, data: CommentCreate, db: DbSession) -> CommentOut:
    """Add a comment to a card."""
    return comments.to_out(comments.create_comment(db, card_id, data))


@router.get("/comments/{comment_id}")
def get_comment(comment_id: int, db: DbSession) -> CommentOut:
    """Get one comment."""
    return comments.to_out(comments.get_comment(db, comment_id))


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_comment(comment_id: int, db: DbSession) -> Response:
    """Delete a comment."""
    comments.delete_comment(db, comment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
