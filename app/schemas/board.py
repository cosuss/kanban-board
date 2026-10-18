"""Board schemas."""

from pydantic import BaseModel, ConfigDict, Field


class BoardCreate(BaseModel):
    """Body for creating a board."""

    name: str = Field(min_length=1)
    repo_url: str | None = None
    with_default_stages: bool = True


class BoardUpdate(BaseModel):
    """Body for partially updating a board."""

    name: str | None = Field(default=None, min_length=1)
    repo_url: str | None = None


class BoardOut(BaseModel):
    """A board as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    repo_url: str | None
