#!/usr/bin/env bash
# Пятничный бэкап Антраши, пока Mac включён и пользователь вошёл в систему.
# launchd вызывает скрипт при входе и раз в час. В один день архив снимается один раз.
#
# Отметка о успехе лежит вне Documents: фоновому заданию macOS не даёт читать эту папку.
#
#   bash scripts/pull-backup-friday.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TODAY="$(date +%Y-%m-%d)"
STATE_DIR="${HOME}/Library/Application Support/Antrasha"
STAMP_FILE="$STATE_DIR/last-db-backup-day"

export PATH="/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin:${PATH:-}"

if [[ -z "${SSH_AUTH_SOCK:-}" ]]; then
  sock="$(launchctl getenv SSH_AUTH_SOCK 2>/dev/null || true)"
  if [[ -n "$sock" ]]; then
    export SSH_AUTH_SOCK="$sock"
  fi
fi

if [[ "$(date +%u)" != "5" ]]; then
  exit 0
fi

mkdir -p "$STATE_DIR"
if [[ -f "$STAMP_FILE" ]] && [[ "$(cat "$STAMP_FILE")" == "$TODAY" ]]; then
  exit 0
fi

LOCK_DIR="$STATE_DIR/db-backup.lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  exit 0
fi
cleanup() { rmdir "$LOCK_DIR" 2>/dev/null || true; }
trap cleanup EXIT

if [[ -f "$STAMP_FILE" ]] && [[ "$(cat "$STAMP_FILE")" == "$TODAY" ]]; then
  exit 0
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') старт пятничного бэкапа"
if bash "$ROOT/scripts/pull-backup.sh"; then
  printf '%s\n' "$TODAY" > "$STAMP_FILE"
  osascript -e 'display notification "Архив лежит в Documents/backups" with title "Бэкап Антраша"' || true
else
  status=$?
  osascript -e 'display notification "Не удалось снять бэкап. Подробности в логе." with title "Бэкап Антраша"' || true
  exit "$status"
fi
