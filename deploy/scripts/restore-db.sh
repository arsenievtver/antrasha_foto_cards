#!/usr/bin/env bash
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

require_cmd docker
ensure_compose
ensure_env_files

DUMP_FILE="${1:-}"
if [[ -z "$DUMP_FILE" ]]; then
  echo "Usage: bash deploy/scripts/restore-db.sh /absolute/path/to/dump.sql.gz"
  exit 1
fi

if [[ ! -f "$DUMP_FILE" ]]; then
  echo "[error] dump file not found: $DUMP_FILE"
  exit 1
fi

POSTGRES_ENV="$DEPLOY_DIR/env/.env.postgres.prod"
POSTGRES_USER="$(awk -F= '/^POSTGRES_USER=/{print $2}' "$POSTGRES_ENV" | tail -n1)"
POSTGRES_DB="$(awk -F= '/^POSTGRES_DB=/{print $2}' "$POSTGRES_ENV" | tail -n1)"

if [[ -z "$POSTGRES_USER" || -z "$POSTGRES_DB" ]]; then
  echo "[error] POSTGRES_USER/POSTGRES_DB missing in $POSTGRES_ENV"
  exit 1
fi

echo "[warn] restoring dump into '$POSTGRES_DB' will overwrite data."
echo "[step] dropping and recreating schema public"
compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"

echo "[step] restoring from $DUMP_FILE"
gzip -dc "$DUMP_FILE" | compose exec -T postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"

echo "[ok] restore completed"
