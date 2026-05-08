#!/usr/bin/env bash
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/lib.sh"

require_cmd docker
ensure_compose
ensure_env_files

BACKUP_DIR="${BACKUP_DIR:-$DEPLOY_DIR/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"
mkdir -p "$BACKUP_DIR"

POSTGRES_ENV="$DEPLOY_DIR/env/.env.postgres.prod"
POSTGRES_USER="$(awk -F= '/^POSTGRES_USER=/{print $2}' "$POSTGRES_ENV" | tail -n1)"
POSTGRES_DB="$(awk -F= '/^POSTGRES_DB=/{print $2}' "$POSTGRES_ENV" | tail -n1)"

if [[ -z "$POSTGRES_USER" || -z "$POSTGRES_DB" ]]; then
  echo "[error] POSTGRES_USER/POSTGRES_DB missing in $POSTGRES_ENV"
  exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_FILE="$BACKUP_DIR/postgres_${POSTGRES_DB}_${STAMP}.sql.gz"

echo "[step] creating dump -> $OUT_FILE"
compose exec -T postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip -9 > "$OUT_FILE"

echo "[step] retention cleanup > ${RETENTION_DAYS} days"
find "$BACKUP_DIR" -type f -name '*.sql.gz' -mtime +"$RETENTION_DAYS" -delete

echo "[ok] backup created: $OUT_FILE"
