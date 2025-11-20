#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required to run this stack." >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  COMPOSE_BIN="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_BIN="docker-compose"
else
  echo "docker compose plugin (or docker-compose) is required." >&2
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required to launch the Flask server." >&2
  exit 1
fi

cd "$ROOT_DIR"

if [[ -f ".env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source ".env"
  set +a
fi

export QB_ENABLED="${QB_ENABLED:-1}"
export QB_URL="${QB_URL:-http://127.0.0.1:8081}"
export QB_USER="${QB_USER:-admin}"
export QB_PASS="${QB_PASS:-adminadmin}"
export QB_CATEGORY="${QB_CATEGORY:-MagnetDrop}"
export TORRENT_JOB_LOG_PATH="${TORRENT_JOB_LOG_PATH:-logs/jobs.jsonl}"

echo "Starting qBittorrent container..."
eval "$COMPOSE_BIN up -d qbittorrent"

container_id="$(eval "$COMPOSE_BIN ps -q qbittorrent")"
if [[ -z "$container_id" ]]; then
  echo "Unable to determine qBittorrent container id." >&2
  exit 1
fi

echo "Waiting for qBittorrent container ($container_id) to become healthy..."
ready=""
for attempt in {1..20}; do
  state="$(docker inspect -f '{{.State.Health.Status}}' "$container_id" 2>/dev/null || true)"
  if [[ "$state" == "healthy" ]]; then
    ready="yes"
    break
  fi

  state="$(docker inspect -f '{{.State.Status}}' "$container_id" 2>/dev/null || true)"
  if [[ "$state" == "running" ]]; then
    ready="yes"
    break
  fi

  sleep 3
done

if [[ -z "$ready" ]]; then
  echo "qBittorrent container failed to report healthy status. Check 'docker compose logs qbittorrent'." >&2
  exit 1
fi

echo "qBittorrent is running. Launching the Flask server..."
exec python3 app.py "$@"
