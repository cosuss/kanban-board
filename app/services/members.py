"""Member rules."""

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Member
from app.schemas.member import MemberCreate, MemberUpdate
from app.services.boards import get_board
from app.services.common import commit_or_conflict, get_or_404

_DUPLICATE = "a member with this github_login already exists"


def list_members(db: Session, board_id: int) -> list[Member]:
    """Return a board's members ordered by id."""
    get_board(db, board_id)
    return list(
        db.scalars(
            select(Member).where(Member.board_id == board_id).order_by(Member.id)
        )
    )


def get_member(db: Session, member_id: int) -> Member:
    """Return one member or raise 404."""
    return get_or_404(db, Member, member_id, "member")


def create_member(db: Session, board_id: int, data: MemberCreate) -> Member:
    """Create a member on a board.

    Returns:
        The new member.

    """
    get_board(db, board_id)
    member = Member(board_id=board_id, **data.model_dump())
    db.add(member)
    commit_or_conflict(db, _DUPLICATE)
    return member


def update_member(db: Session, member_id: int, data: MemberUpdate) -> Member:
    """Apply a partial update.

    Returns:
        The updated member.

    """
    member = get_member(db, member_id)
    for field in ("github_login", "name"):
        value = getattr(data, field)
        if value is not None:
            setattr(member, field, value)
    if "role" in data.model_fields_set:
        member.role = data.role
    commit_or_conflict(db, _DUPLICATE)
    return member


def delete_member(db: Session, member_id: int) -> None:
    """Delete a member; their cards and comments keep existing without an owner."""
    member = get_member(db, member_id)
    db.execute(delete(Member).where(Member.id == member.id))
    db.commit()
