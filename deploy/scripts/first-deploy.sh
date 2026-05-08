#!/usr/bin/env bash
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

require_cmd docker
ensure_compose

mkdir -p "$DEPLOY_DIR/env" "$DEPLOY_DIR/nginx/certs"

cp -n "$DEPLOY_DIR/env/.env.prod.example" "$DEPLOY_DIR/env/.env.prod" || true
cp -n "$DEPLOY_DIR/env/.env.backend.prod.example" "$DEPLOY_DIR/env/.env.backend.prod" || true
cp -n "$DEPLOY_DIR/env/.env.postgres.prod.example" "$DEPLOY_DIR/env/.env.postgres.prod" || true

ensure_env_files

echo "[step] building and starting containers"
compose up -d --build

echo "[step] waiting for backend health"
sleep 6
compose ps

echo "[step] applying database migrations"
compose exec -T backend alembic upgrade head

echo "[ok] first deploy done"
echo "Next: test health endpoint -> curl -I http://127.0.0.1/health"
