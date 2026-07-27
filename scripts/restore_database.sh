#!/bin/bash

set -e

if [ -z "$1" ]; then
  echo "Usage: ./scripts/restore_database.sh <backup-file>"
  exit 1
fi

BACKUP_FILE="$1"

if [ ! -f "$BACKUP_FILE" ]; then
  echo "Backup file not found: $BACKUP_FILE"
  exit 1
fi

cat "$BACKUP_FILE" | docker exec -i helpdesk-postgres psql \
  -U helpdesk \
  -d helpdesk

echo "Database restored from: $BACKUP_FILE"
