#!/usr/bin/env bash
# Запуск Postgres (Docker), миграции, API, основного Vite и админки.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib.sh"
load_dev_env
vite_dev_clear_direct_api_env

COMPOSE="${REPO_ROOT}/backend/docker-compose.yml"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
ADMIN_PORT="${ADMIN_PORT:-5174}"
PID_BACKEND="$SCRIPT_DIR/.backend.pid"
PID_INGEST="$SCRIPT_DIR/.ai-ingest-worker.pid"
PID_FRONT="$SCRIPT_DIR/.frontend.pid"
PID_ADMIN="$SCRIPT_DIR/.admin.pid"
LOG_BACKEND="$SCRIPT_DIR/logs-backend.txt"
LOG_INGEST="$SCRIPT_DIR/logs-ai-ingest-worker.txt"
LOG_FRONT="$SCRIPT_DIR/logs-frontend.txt"
LOG_ADMIN="$SCRIPT_DIR/logs-admin.txt"

ensure_backend_venv
# shellcheck disable=SC1091
source "$REPO_ROOT/backend/.venv/bin/activate"

if [[ "${SKIP_DOCKER_DB:-0}" != "1" ]]; then
	echo "[up] Postgres (Docker): docker compose up -d"
	docker compose -f "$COMPOSE" --project-directory "${REPO_ROOT}/backend" up -d
else
	echo "[up] SKIP_DOCKER_DB=1 — контейнер Postgres не поднимаю"
fi

echo "[up] ожидание PostgreSQL..."
"$SCRIPT_DIR/wait-for-pg.sh"

if [[ -n "${POSTGRES_SUPERUSER:-}" ]]; then
	echo "[up] создание роли/БД (суперпользователь задан)..."
	"$SCRIPT_DIR/db-init.sh"
fi

echo "[up] миграции Alembic..."
cd "$REPO_ROOT/backend"
alembic upgrade head
cd "$REPO_ROOT"

if [[ -f "$PID_BACKEND" ]] && kill -0 "$(cat "$PID_BACKEND")" 2>/dev/null; then
	echo "[up] backend уже запущен (PID $(cat "$PID_BACKEND")) — пропуск"
else
	UVICORN_RELOAD="${UVICORN_RELOAD:-}"
	UV_CMD=(uvicorn app.main:app --host 0.0.0.0 --port "$BACKEND_PORT")
	if [[ "$UVICORN_RELOAD" == "1" ]]; then
		UV_CMD+=(--reload)
	fi
	(
		cd "$REPO_ROOT/backend"
		nohup "${UV_CMD[@]}" >"$LOG_BACKEND" 2>&1 &
		echo $! >"$PID_BACKEND"
	)
	echo "[up] backend http://127.0.0.1:${BACKEND_PORT} (лог: $LOG_BACKEND, PID: $PID_BACKEND)"
fi

if [[ "${SKIP_AI_INGEST_WORKER:-0}" == "1" ]]; then
	echo "[up] SKIP_AI_INGEST_WORKER=1 — воркер очереди ИИ не поднимаю"
elif [[ -f "$PID_INGEST" ]] && kill -0 "$(cat "$PID_INGEST")" 2>/dev/null; then
	echo "[up] ai-ingest worker уже запущен (PID $(cat "$PID_INGEST")) — пропуск"
else
	(
		cd "$REPO_ROOT/backend"
		nohup python -m jobs.ai_ingest_worker >"$LOG_INGEST" 2>&1 &
		echo $! >"$PID_INGEST"
	)
	echo "[up] ai-ingest worker (лог: $LOG_INGEST, PID: $PID_INGEST)"
fi

if [[ -f "$PID_FRONT" ]] && kill -0 "$(cat "$PID_FRONT")" 2>/dev/null; then
	echo "[up] frontend уже запущен (PID $(cat "$PID_FRONT")) — пропуск"
else
	(
		cd "$REPO_ROOT"
		nohup npm run dev -- --host --port "$FRONTEND_PORT" >"$LOG_FRONT" 2>&1 &
		echo $! >"$PID_FRONT"
	)
	echo "[up] frontend http://127.0.0.1:${FRONTEND_PORT} (лог: $LOG_FRONT, PID: $PID_FRONT)"
fi

if [[ "${SKIP_ADMIN:-0}" == "1" ]]; then
	echo "[up] SKIP_ADMIN=1 — админку не поднимаю"
elif [[ ! -d "$REPO_ROOT/admin/node_modules" ]]; then
	echo "[up] админка пропущена: нет admin/node_modules — выполни: npm install --prefix admin"
elif [[ -f "$PID_ADMIN" ]] && kill -0 "$(cat "$PID_ADMIN")" 2>/dev/null; then
	echo "[up] админка уже запущена (PID $(cat "$PID_ADMIN")) — пропуск"
else
	(
		cd "$REPO_ROOT/admin"
		nohup npm run dev -- --host --port "$ADMIN_PORT" >"$LOG_ADMIN" 2>&1 &
		echo $! >"$PID_ADMIN"
	)
	echo "[up] админка http://127.0.0.1:${ADMIN_PORT} (лог: $LOG_ADMIN, PID: $PID_ADMIN)"
fi

echo
echo "──────────────────────────────────────────────────────────────"
echo "Приложение:   http://127.0.0.1:${FRONTEND_PORT}"
echo "Админка:      http://127.0.0.1:${ADMIN_PORT}"
echo "С телефона (та же Wi‑Fi), открой в браузере:"
n=0
while read -r lan_ip; do
	[[ -z "$lan_ip" ]] && continue
	((n++)) || true
	echo "              приложение http://${lan_ip}:${FRONTEND_PORT}"
	echo "              админка    http://${lan_ip}:${ADMIN_PORT}"
done < <(list_lan_ipv4 | sort -u)
if ((n == 0)); then
	echo "              (IP не определён — в macOS: ipconfig getifaddr en0  или вручную IP из «Системные настройки → Сеть»)"
fi
echo "(API: оба Vite — только proxy /api → :${BACKEND_PORT}; VITE_BACKEND_ORIGIN/VITE_API_BASE для dev очищены — см. vite_dev_clear_direct_api_env в scripts/lib.sh)"
echo "(Firewall: TCP ${FRONTEND_PORT}, ${ADMIN_PORT}; прямой доступ к API с телефона — при необходимости откройте ${BACKEND_PORT})"
echo "──────────────────────────────────────────────────────────────"
echo "Готово. Остановка: scripts/dev-down.sh"
