"""Comment schemas."""

from datetime import datetime
from typing import Self

from pydantic import BaseModel, Field, model_validator


class CommentCreate(BaseModel):
    """Body for creating a comment; the author is optional."""

    body: str = Field(min_length=1, max_length=10_000)
    author: str | None = Field(default=None, max_length=255)
    author_id: int | None = None

    @model_validator(mode="after")
    def _author_or_id(self) -> Self:
        if self.author is not None and self.author_id is not None:
            msg = "give either author or author_id, not both"
            raise ValueError(msg)
        return self


class CommentOut(BaseModel):
    """A comment as returned by the API."""

    id: int
    card_id: int
    author_id: int | None
    author: str | None
    author_name: str | None
    body: str
    created_at: datetime
