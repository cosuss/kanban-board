"""FastAPI application."""

from fastapi import APIRouter, FastAPI

from app.api.routes import boards, cards, comments, health, members, milestones, stages
from app.core.errors import register_error_handlers

API_PREFIX = "/api/v1"

api = APIRouter(prefix=API_PREFIX)
for module in (boards, members, stages, milestones, cards, comments, health):
    api.include_router(module.router)

app = FastAPI(title="Kanban Board API", version="0.1.0")
register_error_handlers(app)
app.include_router(api)
# 편의용: /health 도 루트에서 바로 응답한다.
app.include_router(health.router, include_in_schema=False)
