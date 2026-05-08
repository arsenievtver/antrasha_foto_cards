#!/usr/bin/env bash
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

require_cmd docker
ensure_compose
ensure_env_files

echo "[step] running certbot renew"
compose run --rm certbot renew --webroot -w /var/www/certbot --non-interactive

echo "[step] reloading nginx"
compose exec -T nginx nginx -s reload

echo "[ok] renew completed"
