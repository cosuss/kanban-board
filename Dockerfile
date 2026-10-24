FROM python:3.11-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.11.29 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN uv sync --locked --no-dev
CMD ["sh", "-c", "uv run --locked --no-dev alembic upgrade head && uv run --locked --no-dev uvicorn app.main:app --host 0.0.0.0 --port 8000"]
