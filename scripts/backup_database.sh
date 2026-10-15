#!/bin/bash
set -Eeuo pipefail
umask 077

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

if (( $# != 0 )); then
    echo "Usage: ./scripts/backup_database.sh" >&2
    exit 1
fi

BACKUP_DIR="$PROJECT_DIR/backups"
mkdir -p "$BACKUP_DIR"

TEMP_FILE="$(mktemp "$BACKUP_DIR/.backup.XXXXXX")"
trap 'rm -f -- "$TEMP_FILE"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

TIMESTAMP="$(date -u +%Y-%m-%d_%H-%M-%S)"
BACKUP_FILE="$BACKUP_DIR/helpdesk_backup_${TIMESTAMP}_${TEMP_FILE##*.}.sql"

docker compose exec -T postgres sh -c \
    'exec pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB"' > "$TEMP_FILE"

if [[ ! -s "$TEMP_FILE" ]]; then
    echo "ERROR: Database backup was empty." >&2
    exit 1
fi

mv -- "$TEMP_FILE" "$BACKUP_FILE"
echo "Database backup created: $BACKUP_FILE"
