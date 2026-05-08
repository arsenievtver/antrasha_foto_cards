#!/usr/bin/env bash
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

require_cmd docker
require_cmd git
require_cmd curl
ensure_compose
ensure_env_files

cd "$REPO_ROOT"

echo "[step] git pull --ff-only"
git pull --ff-only

echo "[step] rebuilding images"
compose build backend frontend admin

echo "[step] restarting services"
compose up -d --remove-orphans

echo "[step] applying migrations"
compose exec -T backend alembic upgrade head

echo "[step] smoke check /health"
for _ in 1 2 3 4 5 6; do
  if curl -fsS "http://127.0.0.1/health" >/dev/null; then
    echo "[ok] update complete"
    exit 0
  fi
  sleep 3
done

echo "[error] health check failed. See logs:"
compose logs --tail=120 nginx backend
echo "Rollback hint: bash deploy/scripts/rollback.sh HEAD~1"
exit 1
