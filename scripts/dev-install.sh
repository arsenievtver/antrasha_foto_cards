#!/usr/bin/env bash
# Установка/обновление зависимостей локальной разработки (корень, admin, work, xfashion, backend venv).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib.sh"

echo "[install] backend Python venv + requirements"
ensure_backend_venv

echo "[install] npm — корень (клиент ANTRASHA)"
(cd "$REPO_ROOT" && npm install)

for spec in "admin:админка" "work:рабочее PWA" "xfashion:лендинг Xfashion" "giftcard:сертификаты"; do
	dir="${spec%%:*}"
	label="${spec##*:}"
	echo "[install] npm — $label ($dir/)"
	npm install --prefix "$REPO_ROOT/$dir"
done

echo "[install] готово. Запуск: npm run dev:up  или  npm run dev:xfashion:up"
