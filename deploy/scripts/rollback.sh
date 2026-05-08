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
compose up -d postgres
set -a
# shellcheck disable=SC1091
source "$DEPLOY_DIR/env/.env.postgres.prod"
set +a
for _i in $(seq 1 60); do
  if compose exec -T postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
compose run --rm --no-deps backend alembic upgrade head
compose up -d --remove-orphans

echo "[ok] rollback deployed at $(git rev-parse --short HEAD)"
