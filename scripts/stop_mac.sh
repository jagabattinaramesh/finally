#!/usr/bin/env bash
# Stop and remove the FinAlly container.
#
# The 'finally-data' volume is preserved so the SQLite database survives
# between runs.

set -euo pipefail

CONTAINER_NAME="finally"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is not installed or not on PATH" >&2
  exit 1
fi

if [[ "$(docker ps -q -f "name=^${CONTAINER_NAME}$")" != "" ]]; then
  echo "Stopping container '$CONTAINER_NAME'..."
  docker stop "$CONTAINER_NAME" >/dev/null
fi

if [[ "$(docker ps -aq -f "name=^${CONTAINER_NAME}$")" != "" ]]; then
  echo "Removing container '$CONTAINER_NAME'..."
  docker rm "$CONTAINER_NAME" >/dev/null
fi

echo "Stopped. Volume 'finally-data' was preserved."
