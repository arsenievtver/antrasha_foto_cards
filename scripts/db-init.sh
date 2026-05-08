#!/usr/bin/env bash
# Создание роли и БД через суперпользователя (локальный Postgres без Docker или предварительная настройка).
# Если POSTGRES_SUPERUSER не задан — скрипт ничего не делает.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib.sh"
load_dev_env

if [[ -z "${POSTGRES_SUPERUSER:-}" ]]; then
	echo "[db-init] POSTGRES_SUPERUSER пуст — создание роли/БД не выполняется."
	exit 0
fi

ensure_backend_venv
# shellcheck disable=SC1091
source "$REPO_ROOT/backend/.venv/bin/activate"
python "$REPO_ROOT/scripts/create_db.py"
