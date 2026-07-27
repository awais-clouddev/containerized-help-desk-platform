#!/bin/bash

set -e

if [ -z "$1" ]; then
  echo "Usage: ./scripts/view_logs.sh <service-name>"
  echo "Example: ./scripts/view_logs.sh api"
  echo "Available services: nginx, frontend, api, postgres, redis"
  exit 1
fi

SERVICE_NAME="$1"

docker compose logs --tail=100 "$SERVICE_NAME"
