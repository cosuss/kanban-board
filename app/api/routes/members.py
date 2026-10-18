"""Member routes."""

from fastapi import APIRouter, Response, status

from app.db.session import DbSession
from app.schemas.member import MemberCreate, MemberOut, MemberUpdate
from app.services import members

router = APIRouter(tags=["members"])


@router.get("/boards/{board_id}/members")
def list_members(board_id: int, db: DbSession) -> list[MemberOut]:
    """List a board's members."""
    return [MemberOut.model_validate(m) for m in members.list_members(db, board_id)]


@router.post("/boards/{board_id}/members", status_code=status.HTTP_201_CREATED)
def create_member(board_id: int, data: MemberCreate, db: DbSession) -> MemberOut:
    """Add a member to a board."""
    return MemberOut.model_validate(members.create_member(db, board_id, data))


@router.get("/members/{member_id}")
def get_member(member_id: int, db: DbSession) -> MemberOut:
    """Get one member."""
    return MemberOut.model_validate(members.get_member(db, member_id))


@router.patch("/members/{member_id}")
def update_member(member_id: int, data: MemberUpdate, db: DbSession) -> MemberOut:
    """Update a member."""
    return MemberOut.model_validate(members.update_member(db, member_id, data))


@router.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_member(member_id: int, db: DbSession) -> Response:
    """Delete a member."""
    members.delete_member(db, member_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
