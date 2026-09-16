#!/usr/bin/env bash
# Деплой только лендинга Xfashion (+ nginx при изменении шаблонов).
# Бэкенд нужен один раз после миграции 045 и API /public/xfashion/*:
#   WITH_BACKEND=1 bash deploy/scripts/update-xfashion.sh
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

require_cmd docker
require_cmd git
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
ACTIVE_TEMPLATE="$DEPLOY_DIR/nginx/templates/default.conf.template"

tls_cert_present() {
  [[ -n "${APP_DOMAIN:-}" ]] || return 1
  compose run --rm --no-deps --entrypoint sh certbot \
    -c "test -f \"/etc/letsencrypt/live/$APP_DOMAIN/fullchain.pem\"" \
    >/dev/null 2>&1
}

if tls_cert_present; then
  cp "$DEPLOY_DIR/nginx/default.tls.conf.template" "$ACTIVE_TEMPLATE"
else
  cp "$DEPLOY_DIR/nginx/default.http.conf.template" "$ACTIVE_TEMPLATE"
fi

echo "[step] up xfashion + nginx"
compose up -d xfashion
compose up -d --force-recreate nginx

echo "[ok] xfashion deploy complete"
echo "Hint: curl -I https://${XFASHION_DOMAIN:-xfashion.pro}/"
