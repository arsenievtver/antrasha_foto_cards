#!/usr/bin/env bash
# Let's Encrypt для XFASHION_DOMAIN (когда APP/ADMIN уже на TLS).
# Сначала нужен self-signed placeholder, иначе nginx не стартует с TLS-шаблоном.
# Certbot не перевыпускает, если live/ создан вручную — перед certonly снимаем placeholder.
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

mkdir -p "$DEPLOY_DIR/nginx/acme"

has_letsencrypt_cert() {
  compose run --rm --no-deps --entrypoint sh certbot \
    -c "test -f \"/etc/letsencrypt/renewal/$DOMAIN.conf\"" \
    >/dev/null 2>&1
}

has_any_cert_files() {
  compose run --rm --no-deps --entrypoint sh certbot \
    -c "test -f \"/etc/letsencrypt/live/$DOMAIN/fullchain.pem\"" \
    >/dev/null 2>&1
}

live_cert_is_letsencrypt() {
  compose run --rm --no-deps --entrypoint sh certbot -c "
    test -f \"/etc/letsencrypt/live/$DOMAIN/fullchain.pem\" &&
    openssl x509 -in \"/etc/letsencrypt/live/$DOMAIN/fullchain.pem\" -noout -issuer 2>/dev/null \
      | grep -qi 'Let.s Encrypt'
  " >/dev/null 2>&1
}

remove_placeholder_cert() {
  echo "[step] remove placeholder / stale live for ${DOMAIN}"
  compose run --rm --no-deps --entrypoint sh certbot -c "
    set -e
    rm -rf \"/etc/letsencrypt/live/$DOMAIN\" \"/etc/letsencrypt/archive/$DOMAIN\"
    rm -f \"/etc/letsencrypt/renewal/$DOMAIN.conf\"
  "
}

write_placeholder_cert() {
  echo "[step] temporary self-signed for ${DOMAIN} (чтобы nginx стартовал)"
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
}

if has_letsencrypt_cert && live_cert_is_letsencrypt; then
  echo "[info] Let's Encrypt для ${DOMAIN} уже на live/fullchain.pem"
  cp "$DEPLOY_DIR/nginx/default.tls.conf.template" \
    "$DEPLOY_DIR/nginx/templates/default.conf.template"
  compose up -d --force-recreate nginx
  echo "[ok] https://${DOMAIN}"
  exit 0
fi

if has_any_cert_files && ! live_cert_is_letsencrypt; then
  echo "[warn] сертификат для ${DOMAIN} не от Let's Encrypt (placeholder или битый live/) — перевыпуск"
  remove_placeholder_cert
elif ! has_any_cert_files; then
  write_placeholder_cert
else
  echo "[info] есть файлы серта без renewal — заменим через ACME"
  remove_placeholder_cert
fi

cp "$DEPLOY_DIR/nginx/default.tls.conf.template" \
  "$DEPLOY_DIR/nginx/templates/default.conf.template"
compose up -d --force-recreate nginx

echo "[step] wait nginx :80"
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS -o /dev/null -w "%{http_code}" "http://127.0.0.1/" -H "Host: ${DOMAIN}" \
    | grep -qE '^[0-9]+$'; then
    break
  fi
  sleep 2
done

code="$(curl -sS -o /dev/null -w "%{http_code}" \
  "http://${DOMAIN}/.well-known/acme-challenge/ping-test" || echo fail)"
echo "  HTTP ${code} for http://${DOMAIN}/.well-known/… (404 ок, refused — DNS/nginx)"

remove_placeholder_cert

echo "[step] issue Let's Encrypt for ${DOMAIN}"
compose run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d "$DOMAIN" \
  --email "$LETSENCRYPT_EMAIL" \
  --agree-tos --no-eff-email --non-interactive

compose up -d --force-recreate nginx
echo "[ok] https://${DOMAIN}"
