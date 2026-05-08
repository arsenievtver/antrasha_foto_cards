#!/usr/bin/env bash
# Обновление прод-сервера после push в git: pull, сборка, миграции, перезапуск, healthcheck.
# Запуск из корня репозитория на сервере, например: cd /opt/antrasha_tinder
#
#   bash deploy/scripts/server-pull-deploy.sh
#   bash deploy/scripts/server-pull-deploy.sh --with-tags   # плюс python -m app.tag_catalog_seed
#
# Эквивалент с флагом тегов: TAG_CATALOG_SEED=1 bash deploy/scripts/update.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export TAG_CATALOG_SEED="${TAG_CATALOG_SEED:-0}"
for arg in "$@"; do
  case "$arg" in
    --with-tags) export TAG_CATALOG_SEED=1 ;;
    -h|--help)
      echo "Usage: bash deploy/scripts/server-pull-deploy.sh [--with-tags]"
      echo "  --with-tags  run tag catalog seed after deploy (see deploy/README.md)"
      exit 0
      ;;
  esac
done
exec bash "$SCRIPT_DIR/update.sh"
