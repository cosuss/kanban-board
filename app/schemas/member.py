"""Member schemas."""

from pydantic import BaseModel, ConfigDict, Field


class MemberCreate(BaseModel):
    """Body for creating a member."""

    github_login: str = Field(min_length=1, max_length=255)
    name: str = Field(min_length=1, max_length=255)
    role: str | None = None


class MemberUpdate(BaseModel):
    """Body for partially updating a member."""

    github_login: str | None = Field(default=None, min_length=1, max_length=255)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    role: str | None = None


class MemberOut(BaseModel):
    """A member as returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    board_id: int
    github_login: str
    name: str
    role: str | None
