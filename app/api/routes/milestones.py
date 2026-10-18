"""Milestone routes."""

from fastapi import APIRouter, Response, status

from app.db.session import DbSession
from app.schemas.milestone import MilestoneCreate, MilestoneOut, MilestoneUpdate
from app.services import milestones

router = APIRouter(tags=["milestones"])


@router.get("/boards/{board_id}/milestones")
def list_milestones(board_id: int, db: DbSession) -> list[MilestoneOut]:
    """List a board's milestones."""
    return [
        MilestoneOut.model_validate(m) for m in milestones.list_milestones(db, board_id)
    ]


@router.post("/boards/{board_id}/milestones", status_code=status.HTTP_201_CREATED)
def create_milestone(
    board_id: int, data: MilestoneCreate, db: DbSession
) -> MilestoneOut:
    """Add a milestone to a board."""
    return MilestoneOut.model_validate(milestones.create_milestone(db, board_id, data))


@router.get("/milestones/{milestone_id}")
def get_milestone(milestone_id: int, db: DbSession) -> MilestoneOut:
    """Get one milestone."""
    return MilestoneOut.model_validate(milestones.get_milestone(db, milestone_id))


@router.patch("/milestones/{milestone_id}")
def update_milestone(
    milestone_id: int, data: MilestoneUpdate, db: DbSession
) -> MilestoneOut:
    """Update a milestone."""
    return MilestoneOut.model_validate(
        milestones.update_milestone(db, milestone_id, data)
    )


@router.delete("/milestones/{milestone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_milestone(milestone_id: int, db: DbSession) -> Response:
    """Delete a milestone."""
    milestones.delete_milestone(db, milestone_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
