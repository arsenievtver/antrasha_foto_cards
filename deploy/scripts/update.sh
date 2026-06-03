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
compose build backend ai-ingest-worker frontend admin

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
#
# ВАЖНО про проверку сертификата: certbot пишет файлы под root и создаёт
# /etc/letsencrypt/live/<домен>/ с правами 0700 root:root. Хост-юзер
# (alex_tver / docker-группа) такие файлы НЕ видит — `test -f` на хосте
# возвращает false, даже когда серт реально есть. Поэтому проверяем наличие
# серта ВНУТРИ контейнера, у которого этот volume смонтирован.
echo "[step] resolve active nginx template (TLS if cert exists, else HTTP)"
set -a
# shellcheck disable=SC1091
source "$DEPLOY_DIR/env/.env.prod"
set +a
ACTIVE_TEMPLATE="$DEPLOY_DIR/nginx/templates/default.conf.template"

tls_cert_present() {
  [[ -n "${APP_DOMAIN:-}" ]] || return 1
  # `compose run --rm certbot` использует сервис certbot из compose.yml (он уже
  # монтирует ./nginx/letsencrypt:/etc/letsencrypt) и запускается под root.
  # --no-deps чтобы не поднимать зависимости, --entrypoint sh чтобы заменить
  # дефолтный certbot-вызов на простой test -f.
  compose run --rm --no-deps --entrypoint sh certbot \
    -c "test -f \"/etc/letsencrypt/live/$APP_DOMAIN/fullchain.pem\"" \
    >/dev/null 2>&1
}

if tls_cert_present; then
  echo "  using TLS template (cert найден внутри контейнера certbot)"
  cp "$DEPLOY_DIR/nginx/default.tls.conf.template" "$ACTIVE_TEMPLATE"
elif [[ -f "$ACTIVE_TEMPLATE" ]] && grep -q "listen 443" "$ACTIVE_TEMPLATE"; then
  # Защитный фолбэк: cert не нашли, но активный шаблон СЕЙЧАС уже TLS.
  # Это значит, что прод реально работает на TLS, а наша проверка по какой-то
  # причине дала false. Не ломаем прод — оставляем TLS-шаблон.
  echo "  WARNING: cert не виден из контейнера, но активный шаблон уже TLS — оставляем TLS"
  cp "$DEPLOY_DIR/nginx/default.tls.conf.template" "$ACTIVE_TEMPLATE"
else
  echo "  using HTTP template (нет TLS-серта для ${APP_DOMAIN:-<unset>})"
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
