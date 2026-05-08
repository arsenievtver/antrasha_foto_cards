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
  docker compose -f "$COMPOSE_FILE" --project-directory "$DEPLOY_DIR" "$@"
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
