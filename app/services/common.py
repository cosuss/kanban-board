"""Helpers shared by the services."""

from typing import TypeVar

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError

T = TypeVar("T")


def get_or_404(db: Session, model: type[T], pk: int, label: str) -> T:
    """Load a row by primary key or raise a 404.

    Args:
        db: The session.
        model: The ORM class.
        pk: The primary key value.
        label: Human name used in the error message.

    Returns:
        The row.

    Raises:
        NotFoundError: If no row has that id.

    """
    row = db.get(model, pk)
    if row is None:
        msg = f"{label} {pk} not found"
        raise NotFoundError(msg)
    return row


def commit_or_conflict(db: Session, message: str) -> None:
    """Commit, turning a database integrity error into a 409.

    Args:
        db: The session.
        message: The 409 detail to report.

    Raises:
        ConflictError: If the database rejects the change.

    """
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(message) from exc


def flush_or_conflict(db: Session, message: str) -> None:
    """Flush pending changes, turning a database integrity error into a 409.

    Args:
        db: The session.
        message: The 409 detail to report.

    Raises:
        ConflictError: If the database rejects the change.

    """
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(message) from exc
