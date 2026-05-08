#!/usr/bin/env bash
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

require_cmd docker
require_cmd git
ensure_compose
ensure_env_files

TARGET_REF="${1:-HEAD~1}"

cd "$REPO_ROOT"

echo "[step] creating safety tag before rollback"
git tag -f "rollback-safety-$(date +%Y%m%d-%H%M%S)" HEAD

echo "[step] checking out $TARGET_REF"
git checkout "$TARGET_REF"

echo "[step] rebuilding/restarting services"
compose build backend frontend admin
compose up -d --remove-orphans
compose exec -T backend alembic upgrade head

echo "[ok] rollback deployed at $(git rev-parse --short HEAD)"
