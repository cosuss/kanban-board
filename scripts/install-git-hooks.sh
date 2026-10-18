#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

git config core.hooksPath .githooks
chmod +x .githooks/pre-commit scripts/check.sh scripts/fix.sh
printf '%s\n' "Git hooks enabled: core.hooksPath=.githooks"
