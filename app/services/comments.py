"""Comment rules."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.errors import NotFoundError
from app.models import Comment, Member
from app.schemas.comment import CommentCreate, CommentOut
from app.services.cards import get_card


def to_out(comment: Comment) -> CommentOut:
    """Flatten a comment (with author loaded) into CommentOut."""
    return CommentOut(
        id=comment.id,
        card_id=comment.card_id,
        author_id=comment.author_id,
        author=comment.author.github_login if comment.author else None,
        author_name=comment.author.name if comment.author else None,
        body=comment.body,
        created_at=comment.created_at,
    )


def get_comment(db: Session, comment_id: int) -> Comment:
    """Return a comment with its author loaded, or raise 404.

    Raises:
        NotFoundError: If the comment does not exist.

    """
    comment = db.scalar(
        select(Comment)
        .where(Comment.id == comment_id)
        .options(joinedload(Comment.author))
        .execution_options(populate_existing=True)
    )
    if comment is None:
        msg = f"comment {comment_id} not found"
        raise NotFoundError(msg)
    return comment


def list_comments(db: Session, card_id: int) -> list[Comment]:
    """Return a card's comments, oldest first."""
    get_card(db, card_id)
    return list(
        db.scalars(
            select(Comment)
            .where(Comment.card_id == card_id)
            .options(joinedload(Comment.author))
            .order_by(Comment.created_at, Comment.id)
        )
    )


def create_comment(db: Session, card_id: int, data: CommentCreate) -> Comment:
    """Create a comment; the author is a member of the card's board.

    Returns:
        The new comment.

    Raises:
        NotFoundError: If the named author is not on the card's board.

    """
    card = get_card(db, card_id)
    author_id = None
    if data.author is not None or data.author_id is not None:
        stmt = select(Member).where(Member.board_id == card.stage.board_id)
        stmt = (
            stmt.where(Member.github_login == data.author)
            if data.author is not None
            else stmt.where(Member.id == data.author_id)
        )
        author = db.scalar(stmt)
        if author is None:
            msg = f"member {data.author or data.author_id!r} not found on board"
            raise NotFoundError(msg)
        author_id = author.id
    comment = Comment(
        card_id=card_id,
        author_id=author_id,
        body=data.body,
        created_at=datetime.now(UTC),
    )
    db.add(comment)
    db.commit()
    return get_comment(db, comment.id)


def delete_comment(db: Session, comment_id: int) -> None:
    """Delete a comment."""
    comment = get_comment(db, comment_id)
    db.delete(comment)
    db.commit()
