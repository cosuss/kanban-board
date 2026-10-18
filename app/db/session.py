"""Engine, session factory, and the FastAPI session dependency."""

from collections.abc import AsyncIterator
from typing import Annotated

from anyio import CancelScope, CapacityLimiter, fail_after, to_thread
from fastapi import Depends, HTTPException, status
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


def build_engine(url: str | None = None) -> Engine:
    """Create an engine using the configured pool settings.

    Args:
        url: Optional database URL; defaults to ``DATABASE_URL``.

    Returns:
        A SQLAlchemy engine. No connection is opened until first use.

    """
    settings = get_settings()
    return create_engine(
        url or settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_timeout=settings.database_pool_timeout,
        pool_pre_ping=settings.database_pool_pre_ping,
    )


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


# Why sessions are admitted through a limiter (see docs/PERFORMANCE_AUDIT.md):
# sync routes run in a 40-thread pool, but the pool only has pool_size +
# max_overflow connections. A finished request keeps its connection until its
# session closes, and FastAPI needs another pool thread to serialize the
# response first. If every thread is already blocked in a pool checkout, no
# thread is left to finish the requests that hold the connections: the app
# stalls until ``pool_timeout`` and answers 500s. Admitting at most as many
# sessions as there are connections means a thread never waits on the pool.
_SESSION_SLOTS = CapacityLimiter(
    get_settings().database_pool_size + get_settings().database_max_overflow
)


async def get_db() -> AsyncIterator[Session]:
    """Yield a database session and close it afterwards.

    Waits (on the event loop, not in a thread) for a free connection slot for at
    most ``DATABASE_POOL_TIMEOUT`` seconds and answers 503 if none frees up.
    Teardown is async so it never needs a worker thread to start.

    Raises:
        HTTPException: 503 when no connection slot frees up in time.

    """
    borrower = object()
    try:
        with fail_after(get_settings().database_pool_timeout):
            await _SESSION_SLOTS.acquire_on_behalf_of(borrower)
    except TimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="database busy, try again",
        ) from exc
    try:
        session = SessionLocal()
        try:
            yield session
        finally:
            with CancelScope(shield=True):
                await to_thread.run_sync(session.close)
    finally:
        _SESSION_SLOTS.release_on_behalf_of(borrower)


DbSession = Annotated[Session, Depends(get_db, scope="function")]
"""``scope="function"`` closes the session when the route returns, before the
response is serialized, so the connection is held as briefly as possible."""
