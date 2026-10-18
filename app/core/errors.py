"""Domain errors raised by services and mapped to HTTP responses."""

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """Base class for errors that become a ``{"detail": ...}`` response."""

    status_code = status.HTTP_400_BAD_REQUEST

    def __init__(self, detail: str) -> None:
        """Store the human-readable message."""
        super().__init__(detail)
        self.detail = detail


class NotFoundError(DomainError):
    """A referenced row does not exist."""

    status_code = status.HTTP_404_NOT_FOUND


class ConflictError(DomainError):
    """A uniqueness or deletion rule was violated."""

    status_code = status.HTTP_409_CONFLICT


class InvalidRequestError(DomainError):
    """The request is well-formed JSON but not acceptable."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT


def _handle_domain_error(_request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, DomainError):  # pragma: no cover - defensive
        raise exc
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


def register_error_handlers(app: FastAPI) -> None:
    """Attach the domain error handler to the application."""
    app.add_exception_handler(DomainError, _handle_domain_error)
