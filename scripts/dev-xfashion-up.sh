#!/usr/bin/env bash
# Локально: Postgres, миграции, API и только Vite лендинга Xfashion (без client/admin/work).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib.sh"
load_dev_env
vite_dev_clear_direct_api_env

COMPOSE="${REPO_ROOT}/backend/docker-compose.yml"
BACKEND_PORT="${BACKEND_PORT:-8000}"
XFASHION_PORT="${XFASHION_PORT:-5176}"
PID_BACKEND="$SCRIPT_DIR/.backend.pid"
PID_XFASHION="$SCRIPT_DIR/.xfashion.pid"
LOG_BACKEND="$SCRIPT_DIR/logs-backend.txt"
LOG_XFASHION="$SCRIPT_DIR/logs-xfashion.txt"

ensure_backend_venv
# shellcheck disable=SC1091
source "$REPO_ROOT/backend/.venv/bin/activate"

if [[ "${SKIP_DOCKER_DB:-0}" != "1" ]]; then
	echo "[xfashion-up] Postgres (Docker)"
	docker compose -f "$COMPOSE" --project-directory "${REPO_ROOT}/backend" up -d
fi

echo "[xfashion-up] ожидание PostgreSQL..."
"$SCRIPT_DIR/wait-for-pg.sh"

if [[ -n "${POSTGRES_SUPERUSER:-}" ]]; then
	"$SCRIPT_DIR/db-init.sh"
fi

echo "[xfashion-up] миграции Alembic..."
cd "$REPO_ROOT/backend"
alembic upgrade head
cd "$REPO_ROOT"

if [[ -f "$PID_BACKEND" ]] && kill -0 "$(cat "$PID_BACKEND")" 2>/dev/null; then
	echo "[xfashion-up] backend уже запущен (PID $(cat "$PID_BACKEND"))"
else
	UVICORN_RELOAD="${UVICORN_RELOAD:-1}"
	UV_CMD=(uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT")
	if [[ "$UVICORN_RELOAD" == "1" ]]; then
		UV_CMD+=(--reload)
	fi
	(
		cd "$REPO_ROOT/backend"
		nohup "${UV_CMD[@]}" >"$LOG_BACKEND" 2>&1 &
		echo $! >"$PID_BACKEND"
	)
	echo "[xfashion-up] backend http://127.0.0.1:${BACKEND_PORT} (лог: $LOG_BACKEND)"
fi

if [[ ! -d "$REPO_ROOT/xfashion/node_modules" ]]; then
	echo "[xfashion-up] нет xfashion/node_modules — запускаю npm install --prefix xfashion"
	npm install --prefix "$REPO_ROOT/xfashion"
fi

if [[ -f "$PID_XFASHION" ]] && kill -0 "$(cat "$PID_XFASHION")" 2>/dev/null; then
	echo "[xfashion-up] Xfashion уже запущен (PID $(cat "$PID_XFASHION"))"
else
	(
		cd "$REPO_ROOT/xfashion"
		nohup npm run dev -- --host --port "$XFASHION_PORT" >"$LOG_XFASHION" 2>&1 &
		echo $! >"$PID_XFASHION"
	)
	echo "[xfashion-up] Xfashion http://127.0.0.1:${XFASHION_PORT} (лог: $LOG_XFASHION)"
fi

echo
echo "──────────────────────────────────────────────────────────────"
echo "Xfashion:     http://127.0.0.1:${XFASHION_PORT}"
echo "Блог:         http://127.0.0.1:${XFASHION_PORT}/blog"
echo "API (proxy):  /api → :${BACKEND_PORT}"
echo "Остановка:    npm run dev:xfashion:down"
echo "──────────────────────────────────────────────────────────────"
