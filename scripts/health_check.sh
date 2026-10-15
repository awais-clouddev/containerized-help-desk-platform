#!/bin/bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

ATTEMPTS="${HEALTH_ATTEMPTS:-12}"
DELAY="${HEALTH_RETRY_DELAY:-2}"
BASE_URL="${HEALTH_BASE_URL:-http://localhost:8090}"

if ! [[ "$ATTEMPTS" =~ ^[1-9][0-9]?$ ]] ||
   ! [[ "$DELAY" =~ ^[0-9]$ ]]; then
    echo "ERROR: HEALTH_ATTEMPTS must be 1–99 and HEALTH_RETRY_DELAY 0–9." >&2
    exit 1
fi

wait_http() {
    local name="$1" url="$2" attempt
    for ((attempt=1; attempt<=ATTEMPTS; attempt++)); do
        if curl -fsS --connect-timeout 2 --max-time 5 "$url" >/dev/null; then
            echo "$name is healthy"
            return 0
        fi
        if (( attempt < ATTEMPTS )); then
            sleep "$DELAY"
        fi
    done
    echo "ERROR: $name failed health checks after $ATTEMPTS attempts." >&2
    return 1
}

echo "Checking Help Desk Platform health..."
wait_http Nginx "$BASE_URL/"
wait_http API "$BASE_URL/api/health"
docker compose ps
echo "Platform health check completed successfully."
