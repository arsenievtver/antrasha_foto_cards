#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$DEPLOY_DIR/.." && pwd)"
COMPOSE_FILE="$DEPLOY_DIR/docker-compose.prod.yml"

export SCRIPT_DIR DEPLOY_DIR REPO_ROOT COMPOSE_FILE

require_cmd() {
  local cmd="$1"
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "[error] command not found: $cmd"
    exit 1
  fi
}

ensure_compose() {
  if [[ ! -f "$COMPOSE_FILE" ]]; then
    echo "[error] compose file not found: $COMPOSE_FILE"
    exit 1
  fi
}

compose() {
  docker compose -f "$COMPOSE_FILE" --project-directory "$DEPLOY_DIR" \
    --env-file "$DEPLOY_DIR/env/.env.prod" "$@"
}

compose_certbot_sh() {
  compose run --rm --no-deps --entrypoint sh certbot "$@"
}

xfashion_domain_resolved() {
  echo "${XFASHION_DOMAIN:-xfashion.pro}"
}

xfashion_letsencrypt_issued() {
  local domain
  domain="$(xfashion_domain_resolved)"
  compose_certbot_sh -c "test -f \"/etc/letsencrypt/renewal/$domain.conf\"" >/dev/null 2>&1
}

xfashion_live_cert_is_letsencrypt() {
  local domain
  domain="$(xfashion_domain_resolved)"
  compose_certbot_sh -c "
    test -f \"/etc/letsencrypt/live/$domain/fullchain.pem\" &&
    openssl x509 -in \"/etc/letsencrypt/live/$domain/fullchain.pem\" -noout -issuer 2>/dev/null \
      | grep -qi 'Let.s Encrypt'
  " >/dev/null 2>&1
}

xfashion_cert_files_present() {
  local domain
  domain="$(xfashion_domain_resolved)"
  compose_certbot_sh -c "test -f \"/etc/letsencrypt/live/$domain/fullchain.pem\"" >/dev/null 2>&1
}

ensure_xfashion_placeholder_cert() {
  local domain
  domain="$(xfashion_domain_resolved)"
  if xfashion_cert_files_present; then
    return 0
  fi
  echo "[step] placeholder TLS cert for ${domain} (иначе nginx не стартует с TLS-шаблоном)"
  compose_certbot_sh -c "
    set -e
    mkdir -p /etc/letsencrypt/live/$domain
    openssl req -x509 -nodes -newkey rsa:2048 -days 3 \
      -keyout /etc/letsencrypt/live/$domain/privkey.pem \
      -out /etc/letsencrypt/live/$domain/fullchain.pem \
      -subj '/CN=$domain'
  "
}

warn_xfashion_tls_if_placeholder() {
  local domain
  domain="$(xfashion_domain_resolved)"
  if xfashion_live_cert_is_letsencrypt; then
    echo "[ok] TLS Let's Encrypt для ${domain} (live/fullchain.pem)"
    return 0
  fi
  if xfashion_letsencrypt_issued; then
    echo ""
    echo "[!] ${domain}: есть renewal.conf, но nginx отдаёт НЕ Let's Encrypt (часто остался placeholder в live/)."
    echo "    bash deploy/scripts/tls-add-xfashion.sh  — после git pull скрипт перевыпустит сертификат"
    echo ""
    return 0
  fi
  if xfashion_cert_files_present; then
    echo ""
    echo "[!] ${domain}: HTTPS открывается, но сертификат НЕ от Let's Encrypt (браузер покажет «подключение не защищено»)."
    echo "    На сервере из каталога репозитория:"
    echo "    bash deploy/scripts/tls-add-xfashion.sh"
    echo ""
    return 0
  fi
  echo ""
  echo "[!] ${domain}: нет файлов TLS — при TLS-шаблоне nginx может не стартовать."
  echo "    bash deploy/scripts/tls-add-xfashion.sh  (или ensure через update.sh)"
  echo ""
}

# Если admin/work попали в APP_DOMAIN_ALIASES, первый server_name в nginx
# перехватит Host и отдаст клиентский frontend на чужом домене.
assert_distinct_edge_domains() {
  local aliases="${APP_DOMAIN_ALIASES:-}"
  local other a
  for other in "${ADMIN_DOMAIN:-}" "${WORK_DOMAIN:-}" "${XFASHION_DOMAIN:-}"; do
    [[ -n "$other" ]] || continue
    if [[ "${APP_DOMAIN:-}" == "$other" ]]; then
      echo "[error] APP_DOMAIN=${APP_DOMAIN} совпадает с ${other} — клиент и этот сервис делят Host"
      exit 1
    fi
    for a in $aliases; do
      if [[ "$a" == "$other" ]]; then
        echo "[error] APP_DOMAIN_ALIASES содержит ${other} — nginx отдаст клиент на этом домене"
        echo "        Уберите ${other} из APP_DOMAIN_ALIASES в deploy/env/.env.prod"
        exit 1
      fi
    done
  done
}

materialize_nginx_template_from_certs() {
  local active_template="$DEPLOY_DIR/nginx/templates/default.conf.template"
  tls_cert_present() {
    [[ -n "${APP_DOMAIN:-}" ]] || return 1
    compose_certbot_sh -c "test -f \"/etc/letsencrypt/live/$APP_DOMAIN/fullchain.pem\"" >/dev/null 2>&1
  }

  if [[ -z "${XFASHION_DOMAIN:-}" ]]; then
    echo "  WARNING: XFASHION_DOMAIN не задан — используем xfashion.pro"
    XFASHION_DOMAIN=xfashion.pro
    export XFASHION_DOMAIN
  fi

  if tls_cert_present; then
    echo "  using TLS template (cert для ${APP_DOMAIN})"
    cp "$DEPLOY_DIR/nginx/default.tls.conf.template" "$active_template"
    ensure_xfashion_placeholder_cert
  elif [[ -f "$active_template" ]] && grep -q "listen 443" "$active_template"; then
    echo "  WARNING: cert APP не виден, активный шаблон уже TLS — оставляем TLS"
    cp "$DEPLOY_DIR/nginx/default.tls.conf.template" "$active_template"
    ensure_xfashion_placeholder_cert
  else
    echo "  using HTTP template (нет TLS-серта для ${APP_DOMAIN:-<unset>})"
    cp "$DEPLOY_DIR/nginx/default.http.conf.template" "$active_template"
  fi
}

ensure_env_files() {
  local missing=0
  local f
  for f in \
    "$DEPLOY_DIR/env/.env.prod" \
    "$DEPLOY_DIR/env/.env.backend.prod" \
    "$DEPLOY_DIR/env/.env.postgres.prod"
  do
    if [[ ! -f "$f" ]]; then
      echo "[error] missing env file: $f"
      missing=1
    fi
  done
  if [[ "$missing" -eq 1 ]]; then
    exit 1
  fi
}
