#!/bin/bash

set -e

BACKUP_DIR="backups"
TIMESTAMP=$(date +"%Y-%m-%d_%H-%M-%S")
BACKUP_FILE="$BACKUP_DIR/helpdesk_backup_$TIMESTAMP.sql"

mkdir -p "$BACKUP_DIR"

docker exec helpdesk-postgres pg_dump \
  -U helpdesk \
  -d helpdesk > "$BACKUP_FILE"

echo "Database backup created: $BACKUP_FILE"
