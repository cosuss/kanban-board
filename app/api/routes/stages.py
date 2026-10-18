"""Stage routes."""

from fastapi import APIRouter, Response, status

from app.db.session import DbSession
from app.schemas.stage import StageCreate, StageOut, StageUpdate
from app.services import stages

router = APIRouter(tags=["stages"])


@router.get("/boards/{board_id}/stages")
def list_stages(board_id: int, db: DbSession) -> list[StageOut]:
    """List a board's stages in position order."""
    return [StageOut.model_validate(s) for s in stages.list_stages(db, board_id)]


@router.post("/boards/{board_id}/stages", status_code=status.HTTP_201_CREATED)
def create_stage(board_id: int, data: StageCreate, db: DbSession) -> StageOut:
    """Add a stage to a board."""
    return StageOut.model_validate(stages.create_stage(db, board_id, data))


@router.get("/stages/{stage_id}")
def get_stage(stage_id: int, db: DbSession) -> StageOut:
    """Get one stage."""
    return StageOut.model_validate(stages.get_stage(db, stage_id))


@router.patch("/stages/{stage_id}")
def update_stage(stage_id: int, data: StageUpdate, db: DbSession) -> StageOut:
    """Update a stage."""
    return StageOut.model_validate(stages.update_stage(db, stage_id, data))


@router.delete("/stages/{stage_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_stage(stage_id: int, db: DbSession) -> Response:
    """Delete an empty stage (409 if it still has cards)."""
    stages.delete_stage(db, stage_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
