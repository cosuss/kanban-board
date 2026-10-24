"""FastAPI application."""

from fastapi import APIRouter, FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError

from app.api.routes import boards, cards, comments, health, members, milestones, stages
from app.core.config import get_settings
from app.core.errors import register_error_handlers

API_PREFIX = "/api/v1"

api = APIRouter(prefix=API_PREFIX)
for module in (boards, members, stages, milestones, cards, comments, health):
    api.include_router(module.router)


def _data_error(_request: Request, _exc: Exception) -> JSONResponse:
    """Answer 422 (not 500) for values Postgres refuses: int64 overflow, NUL byte."""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": "a value is out of range or contains invalid characters"},
    )


app = FastAPI(title="Kanban Board API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)
register_error_handlers(app)
app.add_exception_handler(DataError, _data_error)
app.include_router(api)
# 편의용: /health 도 루트에서 바로 응답한다.
app.include_router(health.router, include_in_schema=False)
