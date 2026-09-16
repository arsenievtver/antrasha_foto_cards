#!/usr/bin/env bash
# Alembic upgrade head (Postgres должен быть доступен).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib.sh"
load_dev_env

COMPOSE="${REPO_ROOT}/backend/docker-compose.yml"

if [[ "${SKIP_DOCKER_DB:-0}" != "1" ]]; then
	if docker compose -f "$COMPOSE" --project-directory "${REPO_ROOT}/backend" ps -q postgres 2>/dev/null | grep -q .; then
		echo "[migrate] Postgres уже в Docker — жду готовности"
	else
		echo "[migrate] поднимаю Postgres (Docker)"
		docker compose -f "$COMPOSE" --project-directory "${REPO_ROOT}/backend" up -d
	fi
	echo "[migrate] ожидание PostgreSQL..."
	"$SCRIPT_DIR/wait-for-pg.sh"
fi

ensure_backend_venv
# shellcheck disable=SC1091
source "$REPO_ROOT/backend/.venv/bin/activate"

echo "[migrate] alembic upgrade head"
cd "$REPO_ROOT/backend"
alembic upgrade head
echo "[migrate] готово"
