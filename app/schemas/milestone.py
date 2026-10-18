"""Milestone schemas."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class MilestoneCreate(BaseModel):
    """Body for creating a milestone."""

    title: str = Field(min_length=1, max_length=255)
    due_on: date | None = None


class MilestoneUpdate(BaseModel):
    """Body for partially updating a milestone."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    due_on: date | None = None


class MilestoneOut(BaseModel):
    """A milestone as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    board_id: int
    title: str
    due_on: date | None
