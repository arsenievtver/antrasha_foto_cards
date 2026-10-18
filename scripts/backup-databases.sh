#!/usr/bin/env bash
# На VPS: дамп Postgres + баннеры + копии .env → tar.gz
# Фото товаров в бакетах Яндекса этот скрипт не трогает.
#
# Обычно запускает scripts/pull-backup.sh с Mac.
#
set -euo pipefail

ROOT="${ANTRASHA_ROOT:-/opt/antrasha_tinder}"
ENV_DIR="${ENV_DIR:-$ROOT/deploy/env}"
BACKUP_ROOT="${BACKUP_ROOT:-$HOME/antrasha-backups}"

if ! docker info >/dev/null 2>&1; then
  echo "Нет доступа к docker" >&2
  exit 1
fi

read_env() {
  local file="$1" key="$2"
  awk -F= -v k="$key" '$1==k {print substr($0, index($0, "=")+1); exit}' "$file"
}

POSTGRES_ENV="$ENV_DIR/.env.postgres.prod"
if [[ ! -r "$POSTGRES_ENV" ]]; then
  echo "Нет $POSTGRES_ENV" >&2
  exit 1
fi
DB_USER="$(read_env "$POSTGRES_ENV" POSTGRES_USER)"
DB_NAME="$(read_env "$POSTGRES_ENV" POSTGRES_DB)"
if [[ -z "$DB_USER" || -z "$DB_NAME" ]]; then
  echo "В $POSTGRES_ENV нет POSTGRES_USER или POSTGRES_DB" >&2
  exit 1
fi

names="$(docker ps --filter name=postgres --format '{{.Names}}')"
DB_CONTAINER="${names%%$'\n'*}"
if [[ -z "$DB_CONTAINER" || "$names" == *$'\n'* ]]; then
  echo "Нужен один контейнер postgres, нашлось:" >&2
  echo "$names" >&2
  exit 1
fi

STAMP="$(date +%Y%m%d_%H%M%S)"
OUT="$BACKUP_ROOT/$STAMP"
mkdir -p "$OUT"

echo "=== Postgres: $DB_NAME ($DB_CONTAINER) ==="
docker exec "$DB_CONTAINER" \
  pg_dump -U "$DB_USER" -d "$DB_NAME" -Fc --no-owner --no-acl \
  > "$OUT/db.dump"

copy_volume() {
  local suffix="$1" dest="$2"
  local found volume
  found="$(docker volume ls --format '{{.Name}}' | grep -E "_${suffix}$" || true)"
  volume="${found%%$'\n'*}"
  if [[ -z "$volume" ]]; then
    echo "Тома *${suffix} нет, пропускаю" >&2
    return 0
  fi
  echo "=== Том $volume ==="
  docker run --rm -v "$volume":/data:ro pgvector/pgvector:pg16 \
    tar -czf - -C /data . > "$dest"
}

copy_volume "antrasha_promo_media" "$OUT/promo-banners.tar.gz"
copy_volume "antrasha_hero_media" "$OUT/hero-banners.tar.gz"
copy_volume "antrasha_home_v2_media" "$OUT/home-v2.tar.gz"
copy_volume "antrasha_modal_video_media" "$OUT/modal-videos.tar.gz"

if [[ -d "$ENV_DIR" ]]; then
  mkdir -p "$OUT/env"
  shopt -s nullglob
  for f in "$ENV_DIR"/.env*; do
    base="$(basename "$f")"
    [[ "$base" == *.example ]] && continue
    cp "$f" "$OUT/env/$base"
    chmod 600 "$OUT/env/$base"
  done
  shopt -u nullglob
fi

ARCHIVE="$BACKUP_ROOT/antrasha-${STAMP}.tar.gz"
tar -czf "$ARCHIVE" -C "$BACKUP_ROOT" "$STAMP"

echo ""
echo "Готово:"
ls -lh "$OUT" "$ARCHIVE"
