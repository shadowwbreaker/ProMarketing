#!/usr/bin/env sh
# PostgreSQL backup with rotation. Run daily from cron on the DB host, e.g.:
#   15 3 * * * DATABASE_URL=... BACKUP_DIR=/backups /opt/promarketing/infra/scripts/backup.sh
# Copy BACKUP_DIR to separate storage (S3 bucket with versioning) — a backup on the same disk is not a backup.
set -eu
: "${DATABASE_URL:?DATABASE_URL is required}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
mkdir -p "$BACKUP_DIR"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
FILE="$BACKUP_DIR/promarketing-$STAMP.dump"
pg_dump --format=custom --no-owner --dbname="$DATABASE_URL" --file="$FILE"
pg_restore --list "$FILE" > /dev/null   # sanity check: the archive is readable
sha256sum "$FILE" > "$FILE.sha256"
find "$BACKUP_DIR" -name 'promarketing-*.dump*' -mtime +"$KEEP_DAYS" -delete
echo "backup ok: $FILE"
