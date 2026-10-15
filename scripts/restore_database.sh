#!/bin/bash
set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

usage() {
    echo "Usage: ./scripts/restore_database.sh <backup-file> [--database <empty-database>]" >&2
}

if (( $# != 1 && $# != 3 )); then
    usage
    exit 1
fi
if [[ -z "${1:-}" ]]; then
    usage
    exit 1
fi
if (( $# == 3 )) && [[ "$2" != "--database" || -z "$3" ]]; then
    usage
    exit 1
fi

BACKUP_FILE="$1"
TARGET_DB="${3:-}"

if [[ ! -f "$BACKUP_FILE" || ! -r "$BACKUP_FILE" || ! -s "$BACKUP_FILE" ]]; then
    echo "ERROR: Backup must be a readable, nonempty SQL file." >&2
    exit 1
fi

# The source database is not cleared or overwritten.
# Restore only into an existing empty database without concurrent writers.
docker compose exec -T postgres sh -c '
    set -eu
    target="${1:-$POSTGRES_DB}"
    objects="$(psql -X -v ON_ERROR_STOP=1 -At \
        -U "$POSTGRES_USER" -d "$target" -c "
        SELECT count(*)
        FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname NOT IN ('\''pg_catalog'\'', '\''information_schema'\'')
          AND n.nspname NOT LIKE '\''pg_toast%'\''
          AND c.relkind IN ('\''r'\'','\''p'\'','\''v'\'','\''m'\'','\''S'\'','\''f'\'');
    ")"
    if [ "$objects" != "0" ]; then
        echo "ERROR: Target database must be empty; no data was overwritten." >&2
        exit 1
    fi
    exec psql -X --single-transaction -v ON_ERROR_STOP=1 \
        -U "$POSTGRES_USER" -d "$target"
' sh "$TARGET_DB" < "$BACKUP_FILE"

echo "Database restore completed successfully."
