#!/usr/bin/env bash
# Start the FinAlly container.
#
# Usage:
#   bash scripts/start_mac.sh            # build image if missing, then run
#   bash scripts/start_mac.sh --build    # force rebuild before running
#   bash scripts/start_mac.sh --open     # open browser when ready
#
# Idempotent: if the container is already running, this is a no-op.

set -euo pipefail

IMAGE_NAME="finally:latest"
CONTAINER_NAME="finally"
VOLUME_NAME="finally-data"
PORT="8000"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

FORCE_BUILD=0
OPEN_BROWSER=0
for arg in "$@"; do
  case "$arg" in
    --build) FORCE_BUILD=1 ;;
    --open)  OPEN_BROWSER=1 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is not installed or not on PATH" >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    echo "No .env found. Copy .env.example to .env and add your OPENROUTER_API_KEY." >&2
  else
    echo "No .env file found at $REPO_ROOT/.env" >&2
  fi
  exit 1
fi

image_exists() {
  docker image inspect "$IMAGE_NAME" >/dev/null 2>&1
}

if [[ "$FORCE_BUILD" -eq 1 ]] || ! image_exists; then
  echo "Building $IMAGE_NAME..."
  docker build -t "$IMAGE_NAME" .
fi

# Is the container already running?
if [[ "$(docker ps -q -f "name=^${CONTAINER_NAME}$")" != "" ]]; then
  echo "Container '$CONTAINER_NAME' already running."
else
  # Stopped container with same name? Remove it so we can re-create cleanly.
  if [[ "$(docker ps -aq -f "name=^${CONTAINER_NAME}$")" != "" ]]; then
    docker rm "$CONTAINER_NAME" >/dev/null
  fi

  echo "Starting container '$CONTAINER_NAME' on port $PORT..."
  docker run -d \
    --name "$CONTAINER_NAME" \
    --env-file .env \
    -v "${VOLUME_NAME}:/app/db" \
    -p "${PORT}:8000" \
    --restart unless-stopped \
    "$IMAGE_NAME" >/dev/null
fi

URL="http://localhost:${PORT}"
echo "FinAlly is starting at ${URL}"
echo "Health check: ${URL}/api/health"

if [[ "$OPEN_BROWSER" -eq 1 ]]; then
  if command -v open >/dev/null 2>&1; then
    open "$URL"
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$URL" >/dev/null 2>&1 || true
  fi
fi
