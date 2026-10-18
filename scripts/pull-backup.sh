#!/usr/bin/env bash
# С Mac: свежий бэкап Антраши с VPS → папка на этом компьютере.
# Нужен вход по SSH-ключу, без пароля: ssh root@89.111.155.24
#
#   bash scripts/pull-backup.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HOST="${BACKUP_HOST:-root@89.111.155.24}"
REMOTE_DIR="${BACKUP_REMOTE_DIR:-antrasha-backups}"
DEST="${BACKUP_DEST:-$HOME/Documents/backups}"

mkdir -p "$DEST"

echo "Кладу скрипт бэкапа на $HOST:~/$REMOTE_DIR"
ssh "$HOST" "mkdir -p ~/$REMOTE_DIR"
scp "$ROOT/scripts/backup-databases.sh" "$HOST:$REMOTE_DIR/backup-databases.sh"

echo "Снимаю бэкап на сервере"
ssh "$HOST" "bash ~/$REMOTE_DIR/backup-databases.sh"

ARCHIVE="$(ssh "$HOST" "ls -1t ~/$REMOTE_DIR/antrasha-*.tar.gz | head -1")"
if [[ -z "$ARCHIVE" ]]; then
  echo "На сервере не появился архив antrasha-*.tar.gz" >&2
  exit 1
fi

echo "Качаю $ARCHIVE"
scp "$HOST:$ARCHIVE" "$DEST/"

echo ""
echo "Готово:"
ls -lh "$DEST/$(basename "$ARCHIVE")"
