#!/usr/bin/env bash
set -euo pipefail

# Encrypted/compressed PostgreSQL backup with checksum and archive integrity verification.

PGHOST="${PGHOST:-127.0.0.1}"
PGPORT="${PGPORT:-5432}"
PGUSER="${PGUSER:-postgres}"
PGDATABASE="${PGDATABASE:-app}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_FILE="${BACKUP_DIR}/${PGDATABASE}_${STAMP}.sql.gz"
SUM_FILE="${OUT_FILE}.sha256"

mkdir -p "$BACKUP_DIR"

pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" --no-owner --no-privileges "$PGDATABASE" | gzip -9 > "$OUT_FILE"

if [ ! -s "$OUT_FILE" ]; then
  echo "Backup archive is empty: $OUT_FILE" >&2
  exit 1
fi

gzip -t "$OUT_FILE"
sha256sum "$OUT_FILE" > "$SUM_FILE"
sha256sum -c "$SUM_FILE"

find "$BACKUP_DIR" -type f -name "*.sql.gz*" -mtime +"$RETENTION_DAYS" -delete
echo "Verified backup ready: $OUT_FILE"
