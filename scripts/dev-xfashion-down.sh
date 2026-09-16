#!/usr/bin/env bash
# Останавливает Vite Xfashion; опционально backend (STOP_BACKEND=1).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib.sh"
load_dev_env

BACKEND_PORT="${BACKEND_PORT:-8000}"
XFASHION_PORT="${XFASHION_PORT:-5176}"
XFASHION_PREVIEW_PORT="${XFASHION_PREVIEW_PORT:-4176}"
PID_BACKEND="$SCRIPT_DIR/.backend.pid"
PID_XFASHION="$SCRIPT_DIR/.xfashion.pid"

stop_by_pidfile() {
	local f="$1"
	local name="$2"
	if [[ -f "$f" ]]; then
		local pid
		pid="$(cat "$f" 2>/dev/null || true)"
		if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
			echo "[xfashion-down] $name (PID $pid) — SIGTERM"
			kill -TERM "$pid" 2>/dev/null || true
			sleep 0.5
			if kill -0 "$pid" 2>/dev/null; then
				kill -KILL "$pid" 2>/dev/null || true
			fi
		fi
		rm -f "$f"
	fi
}

stop_by_pidfile "$PID_XFASHION" "xfashion (vite)"
kill_port "$XFASHION_PORT"
kill_port "$XFASHION_PREVIEW_PORT"

if [[ "${STOP_BACKEND:-0}" == "1" ]]; then
	stop_by_pidfile "$PID_BACKEND" "backend"
	kill_port "$BACKEND_PORT"
fi

echo "[xfashion-down] готово"
