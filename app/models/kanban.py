"""ORM mappings that mirror the assignment #5 (v3) schema exactly."""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def _pk() -> Mapped[int]:
    return mapped_column(BigInteger, Identity(always=True), primary_key=True)


class Board(Base):
    """A kanban board; one board per GitHub repository."""

    __tablename__ = "boards"

    id: Mapped[int] = _pk()
    name: Mapped[str] = mapped_column(Text)
    repo_url: Mapped[str | None] = mapped_column(Text, unique=True)


class Member(Base):
    """A team member identified by GitHub login."""

    __tablename__ = "members"

    id: Mapped[int] = _pk()
    board_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("boards.id", ondelete="CASCADE")
    )
    github_login: Mapped[str] = mapped_column(Text, unique=True)
    name: Mapped[str] = mapped_column(Text)
    role: Mapped[str | None] = mapped_column(Text)


class Stage(Base):
    """A vertical column of the board (Todo / In Progress / Done)."""

    __tablename__ = "stages"
    __table_args__ = (
        UniqueConstraint("board_id", "name"),
        UniqueConstraint("board_id", "position"),
    )

    id: Mapped[int] = _pk()
    board_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("boards.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)


class Milestone(Base):
    """A goal with an optional due date."""

    __tablename__ = "milestones"
    __table_args__ = (UniqueConstraint("board_id", "title"),)

    id: Mapped[int] = _pk()
    board_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("boards.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(Text)
    due_on: Mapped[date | None] = mapped_column(Date)


class Card(Base):
    """A card, which is a GitHub issue. Its state is its stage."""

    __tablename__ = "cards"
    __table_args__ = (
        Index("idx_cards_stage_id", "stage_id"),
        Index("idx_cards_assignee_id", "assignee_id"),
        Index("idx_cards_milestone_id", "milestone_id"),
    )

    id: Mapped[int] = _pk()
    stage_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stages.id", ondelete="RESTRICT")
    )
    assignee_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("members.id", ondelete="SET NULL")
    )
    milestone_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("milestones.id", ondelete="SET NULL")
    )
    issue_number: Mapped[int] = mapped_column(Integer, unique=True)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    stage: Mapped[Stage] = relationship()
    assignee: Mapped[Member | None] = relationship()
    milestone: Mapped[Milestone | None] = relationship()


class Comment(Base):
    """A comment on a card."""

    __tablename__ = "comments"
    __table_args__ = (
        Index("idx_comments_card_id", "card_id"),
        Index("idx_comments_author_id", "author_id"),
    )

    id: Mapped[int] = _pk()
    card_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("cards.id", ondelete="CASCADE")
    )
    author_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("members.id", ondelete="SET NULL")
    )
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    author: Mapped[Member | None] = relationship()
