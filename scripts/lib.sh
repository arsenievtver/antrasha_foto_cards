#!/usr/bin/env bash
# Общие функции для dev-скриптов: source "$(dirname "$0")/lib.sh"
set -euo pipefail

_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$_LIB_DIR/.." && pwd)"
export REPO_ROOT

load_dev_env() {
	if [[ -f "$REPO_ROOT/.env" ]]; then
		set -a
		# shellcheck disable=SC1090,SC1091
		source "$REPO_ROOT/.env"
		set +a
	fi
	if [[ -f "$REPO_ROOT/backend/.env" ]]; then
		set -a
		# shellcheck disable=SC1090,SC1091
		source "$REPO_ROOT/backend/.env"
		set +a
	fi
}

# Для `npm run dev` приложение и админка должны ходить в API через proxy `/api`.
# Иначе Vite подхватит VITE_* из .env и запросы уйдут мимо прокси (HTML 404, «не JSON»).
# Отключить очистку: DEV_USE_VITE_PROXY=0 scripts/dev-up.sh
vite_dev_clear_direct_api_env() {
	if [[ "${DEV_USE_VITE_PROXY:-1}" != "1" ]]; then
		return 0
	fi
	unset VITE_BACKEND_ORIGIN VITE_API_BASE 2>/dev/null || true
}

kill_port() {
	local port="$1"
	if ! command -v lsof >/dev/null 2>&1; then
		echo "[warn] lsof не найден — пропуск очистки порта $port"
		return 0
	fi
	local pids
	pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
	if [[ -n "$pids" ]]; then
		echo "[stop] освобождаю порт $port (PID: $pids)"
		kill -TERM $pids 2>/dev/null || true
		sleep 0.3
		pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
		if [[ -n "$pids" ]]; then
			kill -KILL $pids 2>/dev/null || true
		fi
	fi
}

ensure_backend_venv() {
	if [[ ! -d "$REPO_ROOT/backend/.venv" ]]; then
		echo "[setup] создаю venv в backend/.venv"
		python3 -m venv "$REPO_ROOT/backend/.venv"
	fi
	# shellcheck disable=SC1091
	source "$REPO_ROOT/backend/.venv/bin/activate"
	pip install -q -r "$REPO_ROOT/backend/requirements.txt"
}

# IPv4 адреса этой машины в LAN (подсказка для доступа с телефона по Wi‑Fi).
list_lan_ipv4() {
	local line
	if command -v ipconfig >/dev/null 2>&1; then
		local i a
		for i in en0 en1 en2 en3 en4; do
			a="$(ipconfig getifaddr "$i" 2>/dev/null || true)"
			[[ -n "$a" ]] && [[ "$a" != "127.0.0.1" ]] && echo "$a"
		done
		return 0
	fi
	if hostname -I &>/dev/null; then
		while read -r line; do
			[[ "$line" =~ ^127\. ]] && continue
			[[ "$line" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] && echo "$line"
		done < <(hostname -I | tr ' ' '\n')
		return 0
	fi
	command -v python3 >/dev/null 2>&1 || return 0
	python3 -c "
import socket
for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
    ip = info[4][0]
    if not ip.startswith('127.'):
        print(ip)
"
}
