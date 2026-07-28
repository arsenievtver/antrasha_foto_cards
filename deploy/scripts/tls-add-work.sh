#!/usr/bin/env bash
# Выпуск Let's Encrypt для WORK_DOMAIN, когда APP/ADMIN уже на TLS.
# Проблема «курицы и яйца»: полный TLS-шаблон требует файл серта work,
# а ACME для work нужен server_name на :80 (иначе default_server → 444).
# Решение: положить короткий self-signed, поднять TLS-шаблон, выпустить
# настоящий серт, пересоздать nginx.
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

require_cmd docker
ensure_compose
ensure_env_files

set -a
# shellcheck disable=SC1091
source "$DEPLOY_DIR/env/.env.prod"
set +a

if [[ -z "${WORK_DOMAIN:-}" || -z "${LETSENCRYPT_EMAIL:-}" ]]; then
  echo "[error] WORK_DOMAIN и LETSENCRYPT_EMAIL должны быть в deploy/env/.env.prod"
  exit 1
fi

LIVE_DIR="$DEPLOY_DIR/nginx/letsencrypt/live/$WORK_DOMAIN"
ARCHIVE_DIR="$DEPLOY_DIR/nginx/letsencrypt/archive/$WORK_DOMAIN"

echo "[step] ensure ACME webroot exists"
mkdir -p "$DEPLOY_DIR/nginx/acme"

# Если настоящего LE-серта ещё нет — кладём self-signed, чтобы nginx
# мог стартовать с блоком listen 443 для WORK_DOMAIN.
need_placeholder=1
if compose run --rm --no-deps --entrypoint sh certbot \
  -c "test -f \"/etc/letsencrypt/live/$WORK_DOMAIN/fullchain.pem\"" \
  >/dev/null 2>&1; then
  # Уже есть файл; если это наш placeholder — certbot всё равно перевыпустит.
  echo "[info] файл серта для ${WORK_DOMAIN} уже есть — продолжаем ACME"
  need_placeholder=0
fi

if [[ "$need_placeholder" == "1" ]]; then
  echo "[step] temporary self-signed for ${WORK_DOMAIN} (чтобы nginx стартовал)"
  mkdir -p "$LIVE_DIR" "$ARCHIVE_DIR"
  # Пишем через контейнер certbot (root), т.к. live/ обычно 0700 root.
  compose run --rm --no-deps --entrypoint sh certbot -c "
    set -e
    mkdir -p /etc/letsencrypt/live/$WORK_DOMAIN /etc/letsencrypt/archive/$WORK_DOMAIN
    if command -v openssl >/dev/null 2>&1; then
      openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
        -keyout /etc/letsencrypt/live/$WORK_DOMAIN/privkey.pem \
        -out /etc/letsencrypt/live/$WORK_DOMAIN/fullchain.pem \
        -subj '/CN=$WORK_DOMAIN'
      cp /etc/letsencrypt/live/$WORK_DOMAIN/fullchain.pem \
         /etc/letsencrypt/live/$WORK_DOMAIN/cert.pem
      ln -sf fullchain.pem /etc/letsencrypt/live/$WORK_DOMAIN/chain.pem 2>/dev/null || true
    else
      echo 'openssl missing in certbot image' >&2
      exit 1
    fi
  "
fi

echo "[step] activate TLS template (с блоком :80 ACME для work)"
cp "$DEPLOY_DIR/nginx/default.tls.conf.template" \
  "$DEPLOY_DIR/nginx/templates/default.conf.template"
compose up -d --force-recreate nginx

echo "[step] wait nginx :80"
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS -o /dev/null -w "%{http_code}" "http://127.0.0.1/" -H "Host: ${WORK_DOMAIN}" \
    | grep -qE '^[0-9]+$'; then
    break
  fi
  sleep 2
done

echo "[step] ACME check from host (должен ответить не connection refused)"
code="$(curl -sS -o /dev/null -w "%{http_code}" \
  "http://${WORK_DOMAIN}/.well-known/acme-challenge/ping-test" || echo fail)"
echo "  HTTP ${code} for http://${WORK_DOMAIN}/.well-known/acme-challenge/… (404 ок, refused — нет)"

echo "[step] issue Let's Encrypt for ${WORK_DOMAIN}"
compose run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d "$WORK_DOMAIN" \
  --email "$LETSENCRYPT_EMAIL" \
  --agree-tos --no-eff-email --non-interactive \
  --force-renewal

echo "[step] reload nginx with real cert"
compose up -d --force-recreate nginx

echo "[ok] https://${WORK_DOMAIN}"
curl -I "https://${WORK_DOMAIN}" || true
