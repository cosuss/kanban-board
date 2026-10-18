"""Card schemas. Stage, assignee, and milestone can be given by name or by id."""

from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, model_validator

_PAIRS = (
    ("stage", "stage_id"),
    ("assignee", "assignee_id"),
    ("milestone", "milestone_id"),
)


class _ReferenceMixin(BaseModel):
    """Rejects requests that give the same reference by name and by id."""

    @model_validator(mode="after")
    def _name_or_id(self) -> Self:
        for name_field, id_field in _PAIRS:
            if getattr(self, name_field) is not None and (
                getattr(self, id_field) is not None
            ):
                msg = f"give either {name_field} or {id_field}, not both"
                raise ValueError(msg)
        return self


class CardCreate(_ReferenceMixin):
    """Body for creating a card."""

    title: str = Field(min_length=1, max_length=255)
    body: str | None = Field(default=None, max_length=10_000)
    stage: str | None = Field(default=None, max_length=255)
    stage_id: int | None = None
    assignee: str | None = Field(default=None, max_length=255)
    assignee_id: int | None = None
    milestone: str | None = Field(default=None, max_length=255)
    milestone_id: int | None = None
    issue_number: int | None = Field(default=None, ge=1, le=2**63 - 1)


class CardUpdate(_ReferenceMixin):
    """Body for partially updating a card (null clears assignee/milestone)."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    body: str | None = Field(default=None, max_length=10_000)
    stage: str | None = Field(default=None, max_length=255)
    stage_id: int | None = None
    assignee: str | None = Field(default=None, max_length=255)
    assignee_id: int | None = None
    milestone: str | None = Field(default=None, max_length=255)
    milestone_id: int | None = None

    @model_validator(mode="after")
    def _stage_not_null(self) -> Self:
        for field in ("stage", "stage_id"):
            if field in self.model_fields_set and getattr(self, field) is None:
                msg = f"{field} cannot be null"
                raise ValueError(msg)
        return self


class CardMove(BaseModel):
    """Body for moving a card to another stage."""

    stage: str | None = Field(default=None, max_length=255)
    stage_id: int | None = None
    position: int | None = Field(default=None, ge=1, le=2**63 - 1)

    @model_validator(mode="after")
    def _exactly_one_target(self) -> Self:
        if (self.stage is None) == (self.stage_id is None):
            msg = "give exactly one of stage or stage_id"
            raise ValueError(msg)
        return self


class CardOut(BaseModel):
    """A card as returned by the API."""

    id: int
    board_id: int
    stage_id: int
    stage: str
    assignee_id: int | None
    assignee: str | None
    assignee_name: str | None
    milestone_id: int | None
    milestone: str | None
    issue_number: int
    title: str
    body: str | None
    position: int
    created_at: datetime
    closed_at: datetime | None
