#!/usr/bin/env bash
# Останавливает Vite, uvicorn, при необходимости освобождает порты и останавливает Docker Postgres.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib.sh"
load_dev_env

COMPOSE="${REPO_ROOT}/backend/docker-compose.yml"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
ADMIN_PORT="${ADMIN_PORT:-5174}"
FRONTEND_PREVIEW_PORT="${FRONTEND_PREVIEW_PORT:-4173}"
ADMIN_PREVIEW_PORT="${ADMIN_PREVIEW_PORT:-4174}"
PID_BACKEND="$SCRIPT_DIR/.backend.pid"
PID_INGEST="$SCRIPT_DIR/.ai-ingest-worker.pid"
PID_FRONT="$SCRIPT_DIR/.frontend.pid"
PID_ADMIN="$SCRIPT_DIR/.admin.pid"

stop_by_pidfile() {
	local f="$1"
	local name="$2"
	if [[ -f "$f" ]]; then
		local pid
		pid="$(cat "$f" 2>/dev/null || true)"
		if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
			echo "[down] $name (PID $pid) — SIGTERM"
			kill -TERM "$pid" 2>/dev/null || true
			sleep 0.5
			if kill -0 "$pid" 2>/dev/null; then
				kill -KILL "$pid" 2>/dev/null || true
			fi
		fi
		rm -f "$f"
	fi
}

stop_by_pidfile "$PID_BACKEND" "backend"
stop_by_pidfile "$PID_INGEST" "ai-ingest worker"
stop_by_pidfile "$PID_FRONT" "frontend"
stop_by_pidfile "$PID_ADMIN" "admin (vite)"

echo "[down] порты $BACKEND_PORT, $FRONTEND_PORT, $ADMIN_PORT, preview $FRONTEND_PREVIEW_PORT и $ADMIN_PREVIEW_PORT"
kill_port "$BACKEND_PORT"
kill_port "$FRONTEND_PORT"
kill_port "$ADMIN_PORT"
kill_port "$FRONTEND_PREVIEW_PORT"
kill_port "$ADMIN_PREVIEW_PORT"

if [[ "${SKIP_DOCKER_DB:-0}" != "1" ]] && [[ "${DOCKER_DOWN:-1}" == "1" ]]; then
	if [[ -f "$COMPOSE" ]]; then
		echo "[down] docker compose stop (Postgres)"
		docker compose -f "$COMPOSE" --project-directory "${REPO_ROOT}/backend" stop
	fi
fi

if [[ "${DOCKER_REMOVE:-0}" == "1" ]] && [[ -f "$COMPOSE" ]]; then
	echo "[down] docker compose down"
	docker compose -f "$COMPOSE" --project-directory "${REPO_ROOT}/backend" down
fi

if [[ "${DOCKER_REMOVE_WITH_VOLUME:-0}" == "1" ]] && [[ -f "$COMPOSE" ]]; then
	echo "[down] docker compose down -v (удаление volume БД)"
	docker compose -f "$COMPOSE" --project-directory "${REPO_ROOT}/backend" down -v
fi

echo "[down] готово"
