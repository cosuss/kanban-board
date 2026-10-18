# Repository guidance

## Python environment

- Use Python 3.11. The `.python-version` file pins the local interpreter, and `pyproject.toml` constrains supported versions to `>=3.11,<3.12`.
- Use `uv` for environment and dependency management. Do not manage this project with a separate `pip` workflow.
- Set up or synchronize the environment with `uv sync --all-groups`.
- Run project commands through `uv run`, for example `uv run uvicorn app.main:app --reload` and `uv run pytest`.
- Add and remove runtime dependencies with `uv add <package>` and `uv remove <package>`. Use `uv add --dev <package>` and `uv remove --dev <package>` for development dependencies.
- Keep `uv.lock` committed and synchronized with `pyproject.toml`. Do not commit `.venv`, `.env`, or Python cache files.
- Ruff is the sole Python linter and formatter (`select = ["ALL"]`, preview). Its strict rule set and format policy live in `pyproject.toml`; do not add conflicting formatters or override its rules casually. When a rule must be ignored, add the narrowest `per-file-ignores` entry with a reason comment.
- Before handing off Python changes, run `uv run ruff check .` and `uv run ruff format --check .`. To apply fixes, run `./scripts/fix.sh`.
- The canonical quality gate is `./scripts/check.sh`. It runs Ruff lint, format check, and the complete pytest suite with locked dependencies. Run it after each meaningful implementation change and before handoff.
- Git pre-commit delegates to the same quality gate. Enable it for a checkout with `./scripts/install-git-hooks.sh`; do not bypass it for normal commits.

## Project conventions

- `docs/DESIGN.md` is the source of every design decision (schema, API, auto-fill rules, CLI, environment variables). Follow it; if a decision must change, change `DESIGN.md` first and say why.
- The backend uses FastAPI, SQLAlchemy 2, psycopg 3, and Alembic on **PostgreSQL only**. There is no SQLite path.
- The database schema is the assignment #5 v3 schema (`side-projects/kanban-db/sql/001_schema.sql`). Do not add columns or tables. Business rules (issue_number, position, closed_at, delete rules) live in `app/services/`, not in the database.
- The Alembic migration is raw SQL with `IF NOT EXISTS` so it is safe on the existing Supabase database. Keep new migrations idempotent in the same way.
- Tests use a real Postgres database (`TEST_DATABASE_URL`, default `postgresql+psycopg://localhost/kanban_test`). Every test starts from truncated tables. Never point `TEST_DATABASE_URL` at the real `kanban` database or Supabase.
- Routes stay thin: parse the request, call a service, return a schema. Services raise `NotFoundError` (404), `ConflictError` (409), or `InvalidRequestError` (422) from `app/core/errors.py`.
- Never commit `.env` or any connection string with a password.
- Bind the unauthenticated local development server to `127.0.0.1` by default.
- The `kanban` CLI (`app/cli/`, entry point `app.cli:app`) is only an HTTP client of the API; it never touches the database except `serve` and `db upgrade`. Every API endpoint needs a matching command, and any new endpoint or option must get a CLI command/option and a test in `tests/test_cli.py` in the same change.
- CLI help text is plain English for non-developers (no "HTTP", "endpoint", "payload", "enum", "pagination"). Requests go through `app.cli.client.request`, so tests swap `get_client` instead of starting a server.

## Agent development loop

1. Read this file and `docs/DESIGN.md` before editing. Turn the requested outcome into observable acceptance criteria.
2. Implement one small vertical slice at a time. Add or update the automated test with the implementation.
3. Run the narrow relevant test while iterating, then run `./scripts/check.sh` before handoff. If a check fails, use its output to fix the code and rerun the gate; do not weaken a rule or delete a failing assertion just to get a green result.
4. Inspect the final diff for unintended changes and update the docs when behavior or design changes.
5. Report what changed and the exact checks run. Never claim a check passed if it was not run.
