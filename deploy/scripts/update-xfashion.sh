#!/usr/bin/env bash
# Деплой только лендинга Xfashion (+ nginx при изменении шаблонов).
# Бэкенд нужен один раз после миграции 045 и API /public/xfashion/*:
#   WITH_BACKEND=1 bash deploy/scripts/update-xfashion.sh
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

require_cmd docker
require_cmd git
require_cmd curl
ensure_compose
ensure_env_files

cd "$REPO_ROOT"

echo "[step] git pull --ff-only"
git pull --ff-only

if [[ "${WITH_BACKEND:-0}" == "1" ]]; then
  echo "[step] rebuild backend (миграции / API xfashion)"
  compose build backend
  compose up -d postgres backend
  compose run --rm --no-deps backend alembic upgrade head
fi

echo "[step] rebuild xfashion"
compose build xfashion

echo "[step] materialize nginx template (same logic as update.sh)"
set -a
# shellcheck disable=SC1091
source "$DEPLOY_DIR/env/.env.prod"
set +a
materialize_nginx_template_from_certs

echo "[step] up xfashion + nginx"
compose up -d xfashion
compose up -d --force-recreate nginx

DOMAIN="$(xfashion_domain_resolved)"
warn_xfashion_tls_if_placeholder

if curl -fsS -o /dev/null --max-time 15 -H "Host: ${DOMAIN}" "http://127.0.0.1/" 2>/dev/null; then
  hdr="$(curl -sS -I --max-time 15 -H "Host: ${DOMAIN}" "http://127.0.0.1/" | tr -d '\r' | awk -F': ' 'tolower($1)=="x-antrasha-app"{print $2; exit}')"
  if [[ "$hdr" == "xfashion" ]]; then
    echo "[ok] nginx → xfashion (X-Antrasha-App=xfashion)"
  else
    echo "[warn] Host ${DOMAIN} → X-Antrasha-App='${hdr:-<empty>}' (ожидали xfashion)"
  fi
fi

echo "[ok] xfashion deploy complete"
echo "Hint: bash deploy/scripts/check-xfashion-tls.sh"
