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

echo "[step] rebuilding images (по одному сервису — меньше шанс OOM на VM 2 GB)"
for _svc in backend ai-ingest-worker frontend admin work xfashion; do
  echo "[step] docker build: $_svc"
  compose build "$_svc"
done

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
materialize_nginx_template_from_certs

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

echo "[step] smoke check /health + app identity (frontend/work containers)"
_header_from_container() {
  local svc="$1"
  # nginx:alpine имеет wget; парсим ответные заголовки
  compose exec -T "$svc" sh -c \
    'wget -S -O /dev/null http://127.0.0.1/ 2>&1' \
    | tr -d '\r' \
    | awk -F': ' 'tolower($1)=="x-antrasha-app"{print tolower($2); exit}'
}

for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS "http://127.0.0.1/health" >/dev/null 2>&1; then
    app_hdr="$(_header_from_container frontend || true)"
    work_hdr="$(_header_from_container work || true)"
    if [[ "$app_hdr" != "client" ]]; then
      echo "[error] container frontend отдал X-Antrasha-App='${app_hdr:-<empty>}' (ожидали client)"
      compose logs --tail=80 frontend work nginx
      exit 1
    fi
    if [[ "$work_hdr" != "work" ]]; then
      echo "[error] container work отдал X-Antrasha-App='${work_hdr:-<empty>}' (ожидали work)"
      compose logs --tail=80 frontend work nginx
      exit 1
    fi
    echo "[ok] app identity: frontend=client, work=work"
    warn_xfashion_tls_if_placeholder
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
