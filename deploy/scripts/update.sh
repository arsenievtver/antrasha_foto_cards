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

echo "[step] ensuring postgres up"
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

echo "[step] apply migrations before rolling backend"
compose run --rm --no-deps backend alembic upgrade head

echo "[step] restarting services"
compose up -d --remove-orphans

echo "[step] smoke check /health (nginx :80 или backend :8000)"
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS "http://127.0.0.1/health" >/dev/null 2>&1; then
    echo "[ok] update complete (nginx)"
    exit 0
  fi
  if curl -fsS "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
    echo "[ok] update complete (backend только; проверь nginx/зависимости)"
    exit 0
  fi
  sleep 3
done

echo "[error] health check failed. See logs:"
compose logs --tail=120 nginx backend
echo "Rollback hint: bash deploy/scripts/rollback.sh HEAD~1"
exit 1
