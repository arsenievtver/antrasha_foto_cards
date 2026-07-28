#!/usr/bin/env bash
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

require_cmd docker
ensure_compose

mkdir -p "$DEPLOY_DIR/env" "$DEPLOY_DIR/nginx/certs"

# Не перетирать уже созданные .env при повторном запуске (портативно без cp -n warnings)
for _pair in \
  ".env.prod.example|.env.prod" \
  ".env.backend.prod.example|.env.backend.prod" \
  ".env.postgres.prod.example|.env.postgres.prod"; do
  _src="$DEPLOY_DIR/env/${_pair%%|*}"
  _dst="$DEPLOY_DIR/env/${_pair##*|}"
  if [[ ! -f "$_dst" ]]; then cp "$_src" "$_dst"; fi
done

ensure_env_files

echo "[step] build images"
compose build backend frontend admin work

echo "[step] start postgres only"
compose up -d postgres

echo "[step] wait for postgres readiness"
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

echo "[step] apply migrations (до старта API — иначе lifespan падает на пустой БД)"
compose run --rm --no-deps backend alembic upgrade head

# Bootstrap активного nginx-шаблона (HTTP-режим). После выпуска сертификатов
# через tls-enable.sh скрипт сам перетрёт шаблон на TLS-вариант. Файл не
# отслеживается git'ом (см. .gitignore), поэтому генерим явно перед `compose up`.
echo "[step] bootstrap nginx template (HTTP mode; TLS enables via tls-enable.sh later)"
cp "$DEPLOY_DIR/nginx/default.http.conf.template" \
   "$DEPLOY_DIR/nginx/templates/default.conf.template"

echo "[step] starting all containers"
compose up -d --remove-orphans

echo "[step] backend health pause"
sleep 6
compose ps

echo "[ok] first deploy done"
echo "Next: curl -fsS http://127.0.0.1:8000/health  затем после nginx → curl -fsS http://127.0.0.1/health"
