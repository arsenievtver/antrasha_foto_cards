#!/usr/bin/env bash
# Let's Encrypt для GIFT_DOMAIN (когда APP/ADMIN уже на TLS).
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

if [[ -z "${GIFT_DOMAIN:-}" || -z "${LETSENCRYPT_EMAIL:-}" ]]; then
  echo "[error] GIFT_DOMAIN и LETSENCRYPT_EMAIL должны быть в deploy/env/.env.prod"
  exit 1
fi

DOMAIN="$GIFT_DOMAIN"

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

# Placeholder снимать до старта nginx нельзя: без файла серта nginx
# не поднимает и :80, и Let’s Encrypt получает connection refused.
if ! has_any_cert_files; then
  write_placeholder_cert
elif ! live_cert_is_letsencrypt; then
  echo "[warn] сертификат для ${DOMAIN} не от Let's Encrypt — nginx стартует на нём, потом перевыпуск"
else
  echo "[info] есть файлы серта без renewal — nginx оставляем на них до ACME"
fi

cp "$DEPLOY_DIR/nginx/default.tls.conf.template" \
  "$DEPLOY_DIR/nginx/templates/default.conf.template"
compose up -d --force-recreate nginx

echo "[step] wait nginx :80"
ready=0
for _ in 1 2 3 4 5 6 7 8 9 10; do
  if curl -fsS -o /dev/null -w "%{http_code}" "http://127.0.0.1/" -H "Host: ${DOMAIN}" \
    | grep -qE '^[0-9]+$'; then
    ready=1
    break
  fi
  sleep 2
done

if [[ "$ready" != "1" ]]; then
  echo "[error] nginx не слушает :80 — сертификат не выпускаем, иначе лягут все сайты"
  compose logs --tail=40 nginx || true
  exit 1
fi

code="$(curl -sS -o /dev/null -w "%{http_code}" \
  "http://${DOMAIN}/.well-known/acme-challenge/ping-test" || echo fail)"
echo "  HTTP ${code} for http://${DOMAIN}/.well-known/… (404 ок, refused — DNS/nginx)"
if [[ "$code" == "000fail" || "$code" == "000" ]]; then
  echo "[error] http://${DOMAIN} не отвечает, ACME не запускаем"
  exit 1
fi

if ! live_cert_is_letsencrypt; then
  remove_placeholder_cert
fi

echo "[step] issue Let's Encrypt for ${DOMAIN}"
if ! compose run --rm certbot certonly \
  --webroot -w /var/www/certbot \
  -d "$DOMAIN" \
  --email "$LETSENCRYPT_EMAIL" \
  --agree-tos --no-eff-email --non-interactive; then
  echo "[error] certbot не выпустил сертификат — возвращаем placeholder, чтобы nginx снова стартовал"
  write_placeholder_cert
  compose up -d --force-recreate nginx
  exit 1
fi

compose up -d --force-recreate nginx
echo "[ok] https://${DOMAIN}"
