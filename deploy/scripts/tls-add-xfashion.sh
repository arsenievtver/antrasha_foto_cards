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

if [[ -z "${XFASHION_DOMAIN:-}" || -z "${LETSENCRYPT_EMAIL:-}" ]]; then
  echo "[error] XFASHION_DOMAIN и LETSENCRYPT_EMAIL должны быть в deploy/env/.env.prod"
  exit 1
fi

DOMAIN="$XFASHION_DOMAIN"
LIVE_DIR="$DEPLOY_DIR/nginx/letsencrypt/live/$DOMAIN"

mkdir -p "$DEPLOY_DIR/nginx/acme"

need_placeholder=1
if compose run --rm --no-deps --entrypoint sh certbot \
  -c "test -f \"/etc/letsencrypt/live/$DOMAIN/fullchain.pem\"" \
  >/dev/null 2>&1; then
  echo "[info] серт для ${DOMAIN} уже есть"
  need_placeholder=0
fi

if [[ "$need_placeholder" == "1" ]]; then
  echo "[step] temporary self-signed for ${DOMAIN}"
  compose run --rm --no-deps --entrypoint sh certbot -c "
    set -e
    mkdir -p /etc/letsencrypt/live/$DOMAIN /etc/letsencrypt/archive/$DOMAIN
    openssl req -x509 -nodes -newkey rsa:2048 -days 1 \
      -keyout /etc/letsencrypt/live/$DOMAIN/privkey.pem \
      -out /etc/letsencrypt/live/$DOMAIN/fullchain.pem \
      -subj '/CN=$DOMAIN'
    cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem \
       /etc/letsencrypt/live/$DOMAIN/cert.pem
  "
fi

cp "$DEPLOY_DIR/nginx/default.tls.conf.template" \
  "$DEPLOY_DIR/nginx/templates/default.conf.template"
compose up -d --force-recreate nginx

echo "[step] issue Let's Encrypt for ${DOMAIN}"
compose run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d "$DOMAIN" \
  --email "$LETSENCRYPT_EMAIL" \
  --agree-tos --no-eff-email --non-interactive \
  --force-renewal

compose up -d --force-recreate nginx
echo "[ok] https://${DOMAIN}"
