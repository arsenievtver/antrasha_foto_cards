#!/usr/bin/env bash
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

echo "[step] rebuilding images"
compose build backend frontend admin

echo "[step] ensuring postgres up"
compose up -d postgres
set -a
# shellcheck disable=SC1091
source "$DEPLOY_DIR/env/.env.postgres.prod"
set +a
for _i in $(seq 1 60); do
  if compose exec -T postgres pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "[step] apply migrations before rolling backend"
compose run --rm --no-deps backend alembic upgrade head

# Активный nginx-шаблон не отслеживается git'ом (см. .gitignore) — он генерится
# здесь из двух источников: default.tls.conf.template (если уже выпущен
# Let's Encrypt сертификат для APP_DOMAIN) или default.http.conf.template
# (иначе). Это устраняет постоянный «локальный diff» на сервере после
# tls-enable.sh, из-за которого git pull рушился.
echo "[step] resolve active nginx template (TLS if cert exists, else HTTP)"
set -a
# shellcheck disable=SC1091
source "$DEPLOY_DIR/env/.env.prod"
set +a
ACTIVE_TEMPLATE="$DEPLOY_DIR/nginx/templates/default.conf.template"
TLS_CERT="$DEPLOY_DIR/nginx/letsencrypt/live/${APP_DOMAIN:-_unset_}/fullchain.pem"
if [[ -n "${APP_DOMAIN:-}" && -f "$TLS_CERT" ]]; then
  echo "  using TLS template (cert: $TLS_CERT)"
  cp "$DEPLOY_DIR/nginx/default.tls.conf.template" "$ACTIVE_TEMPLATE"
else
  echo "  using HTTP template (no TLS cert for ${APP_DOMAIN:-<unset>})"
  cp "$DEPLOY_DIR/nginx/default.http.conf.template" "$ACTIVE_TEMPLATE"
fi

echo "[step] restarting services"
compose up -d --remove-orphans
# bind-mount файла не триггерит recreate, а envsubst шаблонов nginx-образа
# выполняется только в entrypoint'е при старте контейнера. Поэтому здесь
# принудительно пересоздаём nginx, чтобы он подхватил обновлённый шаблон.
compose up -d --force-recreate nginx

if [[ "${TAG_CATALOG_SEED:-0}" == "1" ]]; then
  echo "[step] tag catalog seed (TAG_CATALOG_SEED=1)"
  compose exec -T backend python -m app.tag_catalog_seed
fi

echo "[step] smoke check /health (nginx :80 или backend :8000)"
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS "http://127.0.0.1/health" >/dev/null 2>&1; then
    echo "[ok] update complete (nginx)"
    exit 0
  fi
  if curl -fsS "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
    echo "[ok] update complete (backend только; проверь nginx/зависимости)"
    exit 0
  fi
  sleep 3
done

echo "[error] health check failed. See logs:"
compose logs --tail=120 nginx backend
echo "Rollback hint: bash deploy/scripts/rollback.sh HEAD~1"
exit 1
