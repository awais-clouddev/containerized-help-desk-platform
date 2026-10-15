#!/bin/bash

set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if [ -z "${1:-}" ]; then
  echo "Usage: ./scripts/view_logs.sh <service-name>"
  echo "Example: ./scripts/view_logs.sh api"
  echo "Available services: nginx, frontend, api, postgres, redis"
  exit 1
fi


case "$1" in
    nginx|frontend|api|postgres|redis) ;;
    *) echo "ERROR: Unknown service name." >&2; exit 1 ;;
esac

SERVICE_NAME="$1"

docker compose logs --tail=100 "$SERVICE_NAME"
