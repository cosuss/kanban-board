"""Stage schemas."""

from pydantic import BaseModel, ConfigDict, Field


class StageCreate(BaseModel):
    """Body for creating a stage; position defaults to the end."""

    name: str = Field(min_length=1, max_length=255)
    position: int | None = Field(default=None, ge=1, le=2**63 - 1)


class StageUpdate(BaseModel):
    """Body for partially updating a stage."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    position: int | None = Field(default=None, ge=1, le=2**63 - 1)


class StageOut(BaseModel):
    """A stage as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    board_id: int
    name: str
    position: int
