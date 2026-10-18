#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

if ! command -v uv >/dev/null 2>&1; then
    printf '%s\n' "Error: uv is required. Install it before running checks." >&2
    exit 1
fi

printf '%s\n' "[check] Ruff lint"
uv run --locked ruff check .

printf '%s\n' "[check] Ruff format"
uv run --locked ruff format --check .

printf '%s\n' "[check] Pytest"
uv run --locked pytest

printf '%s\n' "[check] All checks passed."
