#!/usr/bin/env bash
# Ждёт готовности PostgreSQL (Docker или локальный pg_isready).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib.sh"
load_dev_env

COMPOSE="${REPO_ROOT}/backend/docker-compose.yml"
TIMEOUT="${PG_WAIT_TIMEOUT:-60}"

wait_with_docker() {
	local i=0
	while [[ $i -lt $TIMEOUT ]]; do
		if docker compose -f "$COMPOSE" --project-directory "${REPO_ROOT}/backend" exec -T db pg_isready -U "${POSTGRES_APP_USER:-antrasha}" -d "${POSTGRES_APP_DB:-antrasha}" >/dev/null 2>&1; then
			echo "[pg] готов (docker exec pg_isready)"
			return 0
		fi
		sleep 1
		((i++)) || true
	done
	return 1
}

wait_with_cli() {
	local host="${POSTGRES_HOST:-localhost}"
	local port="${POSTGRES_PORT:-5433}"
	local user="${POSTGRES_APP_USER:-antrasha}"
	local db="${POSTGRES_APP_DB:-antrasha}"
	export PGPASSWORD="${POSTGRES_APP_PASSWORD:-antrasha}"
	local i=0
	while [[ $i -lt $TIMEOUT ]]; do
		if command -v pg_isready >/dev/null 2>&1; then
			if pg_isready -h "$host" -p "$port" -U "$user" -d "$db" >/dev/null 2>&1; then
				echo "[pg] готов (pg_isready $host:$port)"
				return 0
			fi
		else
			echo "[pg] pg_isready не найден — полагаюсь на docker exec"
			wait_with_docker && return 0
			return 1
		fi
		sleep 1
		((i++)) || true
	done
	return 1
}

if [[ "${SKIP_DOCKER_DB:-0}" == "1" ]]; then
	echo "[pg] SKIP_DOCKER_DB=1 — жду Postgres на хосте (без Docker)"
	host="${POSTGRES_HOST:-localhost}"
	port="${POSTGRES_PORT:-5432}"
	user="${POSTGRES_APP_USER:-antrasha}"
	db="${POSTGRES_APP_DB:-antrasha}"
	export PGPASSWORD="${POSTGRES_APP_PASSWORD:-antrasha}"
	if ! command -v pg_isready >/dev/null 2>&1; then
		echo "[pg] установите клиент Postgres (например brew install libpq) для pg_isready"
		exit 1
	fi
	i=0
	while [[ $i -lt $TIMEOUT ]]; do
		if pg_isready -h "$host" -p "$port" -U "$user" -d "$db" >/dev/null 2>&1; then
			echo "[pg] готов ($host:$port)"
			exit 0
		fi
		sleep 1
		((i++)) || true
	done
	echo "[pg] таймаут ${TIMEOUT}s — $host:$port"
	exit 1
fi

if [[ ! -f "$COMPOSE" ]]; then
	echo "Не найден $COMPOSE"
	exit 1
fi

if ! docker compose -f "$COMPOSE" --project-directory "${REPO_ROOT}/backend" ps --status running --quiet db >/dev/null 2>&1; then
	echo "[pg] контейнер db не запущен — сначала docker compose up"
	exit 1
fi

if wait_with_docker; then
	exit 0
fi
echo "[pg] пробую pg_isready с хоста..."
if wait_with_cli; then
	exit 0
fi

echo "[pg] таймаут ${TIMEOUT}s — Postgres недоступен"
exit 1
