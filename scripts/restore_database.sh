#!/bin/bash

set -euo pipefail

if [ -z "$1" ]; then
  echo "Usage: ./scripts/restore_database.sh <backup-file>"
  exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "Backup file not found: $BACKUP_FILE"
  exit 1
fi

docker exec -i helpdesk-postgres psql \
  -X -v ON_ERROR_STOP=1 \
  -U helpdesk \
  -d helpdesk < "$BACKUP_FILE"

echo "Database restored from: $BACKUP_FILE"
