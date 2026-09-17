#!/usr/bin/env bash
# Проверка xfashion.pro с хоста (DNS, HTTP→HTTPS, тип сертификата).
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

set -a
# shellcheck disable=SC1091
source "$DEPLOY_DIR/env/.env.prod"
set +a

DOMAIN="${XFASHION_DOMAIN:-xfashion.pro}"

require_cmd curl
require_cmd openssl

echo "=== ${DOMAIN} (с этой машины) ==="
echo -n "DNS A: "
getent ahosts "$DOMAIN" 2>/dev/null | awk '{print $1}' | head -3 | tr '\n' ' ' || true
echo ""

code_http="$(curl -sS -o /dev/null -w "%{http_code}" --max-time 15 "http://${DOMAIN}/" || echo err)"
echo "HTTP /  → ${code_http} (301 на https — норма)"

if ! code_https="$(curl -sS -o /dev/null -w "%{http_code}" --max-time 15 "https://${DOMAIN}/" 2>/dev/null)"; then
  echo "HTTPS / → ошибка TLS (curl не доверяет сертификату — типично для placeholder)"
  code_https="tls_err"
else
  echo "HTTPS / → ${code_https}"
fi

issuer="$(echo | openssl s_client -connect "${DOMAIN}:443" -servername "$DOMAIN" 2>/dev/null \
  | openssl x509 -noout -issuer 2>/dev/null || echo unknown)"
echo "Cert issuer: ${issuer}"

if compose_certbot_sh -c "test -f /etc/letsencrypt/renewal/${DOMAIN}.conf" 2>/dev/null; then
  echo "Docker LE renewal: да (/etc/letsencrypt/renewal/${DOMAIN}.conf)"
else
  echo "Docker LE renewal: нет"
fi

live_issuer="$(compose_certbot_sh -c "openssl x509 -in /etc/letsencrypt/live/${DOMAIN}/fullchain.pem -noout -issuer 2>/dev/null" 2>/dev/null || true)"
if [[ -n "$live_issuer" ]]; then
  echo "Docker live issuer: ${live_issuer}"
fi

if [[ "$issuer" == *"Let's Encrypt"* ]]; then
  echo "[ok] Снаружи виден доверенный Let's Encrypt"
elif [[ "$issuer" == *"${DOMAIN}"* ]]; then
  echo "[!] Снаружи self-signed placeholder — браузеры блокируют."
  echo "    git pull && bash deploy/scripts/tls-add-xfashion.sh  (скрипт снимет placeholder и выпустит LE)"
else
  echo "[?] Проверь issuer вручную"
fi
