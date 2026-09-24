#!/usr/bin/env bash
# Локально: Postgres, миграции, API и только Vite сертификатов.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib.sh"
load_dev_env
vite_dev_clear_direct_api_env

COMPOSE="${REPO_ROOT}/backend/docker-compose.yml"
BACKEND_PORT="${BACKEND_PORT:-8000}"
GIFTCARD_PORT="${GIFTCARD_PORT:-5177}"
PID_BACKEND="$SCRIPT_DIR/.backend.pid"
PID_GIFTCARD="$SCRIPT_DIR/.giftcard.pid"
LOG_BACKEND="$SCRIPT_DIR/logs-backend.txt"
LOG_GIFTCARD="$SCRIPT_DIR/logs-giftcard.txt"

ensure_backend_venv
# shellcheck disable=SC1091
source "$REPO_ROOT/backend/.venv/bin/activate"

if [[ "${SKIP_DOCKER_DB:-0}" != "1" ]]; then
	echo "[giftcard-up] Postgres (Docker)"
	docker compose -f "$COMPOSE" --project-directory "${REPO_ROOT}/backend" up -d
fi

echo "[giftcard-up] ожидание PostgreSQL..."
"$SCRIPT_DIR/wait-for-pg.sh"

if [[ -n "${POSTGRES_SUPERUSER:-}" ]]; then
	"$SCRIPT_DIR/db-init.sh"
fi

echo "[giftcard-up] миграции Alembic..."
cd "$REPO_ROOT/backend"
alembic upgrade head
cd "$REPO_ROOT"

if [[ -f "$PID_BACKEND" ]] && kill -0 "$(cat "$PID_BACKEND")" 2>/dev/null; then
	echo "[giftcard-up] backend уже запущен (PID $(cat "$PID_BACKEND"))"
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
	echo "[giftcard-up] backend http://127.0.0.1:${BACKEND_PORT} (лог: $LOG_BACKEND)"
fi

if [[ ! -d "$REPO_ROOT/giftcard/node_modules" ]]; then
	echo "[giftcard-up] нет giftcard/node_modules — запускаю npm install --prefix giftcard"
	npm install --prefix "$REPO_ROOT/giftcard"
fi

if [[ -f "$PID_GIFTCARD" ]] && kill -0 "$(cat "$PID_GIFTCARD")" 2>/dev/null; then
	echo "[giftcard-up] сертификаты уже запущены (PID $(cat "$PID_GIFTCARD"))"
else
	(
		cd "$REPO_ROOT/giftcard"
		nohup npm run dev -- --host --port "$GIFTCARD_PORT" >"$LOG_GIFTCARD" 2>&1 &
		echo $! >"$PID_GIFTCARD"
	)
	echo "[giftcard-up] сертификаты http://127.0.0.1:${GIFTCARD_PORT} (лог: $LOG_GIFTCARD)"
fi

echo
echo "──────────────────────────────────────────────────────────────"
echo "Сертификаты: http://127.0.0.1:${GIFTCARD_PORT}"
echo "API (proxy): /api → :${BACKEND_PORT}"
echo "Остановка:   npm run dev:giftcard:down"
echo "──────────────────────────────────────────────────────────────"
