#!/usr/bin/env bash
# Генерация VAPID-ключей для Web Push (использует backend/.venv).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/lib.sh"
ensure_backend_venv
python "$ROOT/backend/scripts/generate_vapid_keys.py"
