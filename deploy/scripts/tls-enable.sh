#!/usr/bin/env bash
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

if [[ -z "${APP_DOMAIN:-}" || -z "${ADMIN_DOMAIN:-}" || -z "${LETSENCRYPT_EMAIL:-}" ]]; then
  echo "[error] APP_DOMAIN, ADMIN_DOMAIN, LETSENCRYPT_EMAIL must be set in deploy/env/.env.prod"
  exit 1
fi

mkdir -p "$DEPLOY_DIR/nginx/letsencrypt" "$DEPLOY_DIR/nginx/acme"

echo "[step] ensuring stack is up in HTTP mode"
compose up -d nginx

echo "[step] issuing cert for ${APP_DOMAIN}"
compose run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d "$APP_DOMAIN" \
  --email "$LETSENCRYPT_EMAIL" \
  --agree-tos --no-eff-email --non-interactive

echo "[step] issuing cert for ${ADMIN_DOMAIN}"
compose run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d "$ADMIN_DOMAIN" \
  --email "$LETSENCRYPT_EMAIL" \
  --agree-tos --no-eff-email --non-interactive

echo "[step] switching nginx template to TLS"
# NB: только один файл *.template в deploy/nginx/templates/ — иначе образ nginx генерит несколько *.conf и падает на лишнем SSL без сертификатов
cp "$DEPLOY_DIR/nginx/default.tls.conf.template" "$DEPLOY_DIR/nginx/templates/default.conf.template"

echo "[step] recreating nginx"
compose up -d --force-recreate nginx

echo "[ok] TLS enabled"
echo "Verify: https://${APP_DOMAIN} and https://${ADMIN_DOMAIN}"
