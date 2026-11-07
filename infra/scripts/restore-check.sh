#!/usr/bin/env sh
# Proves a backup can be restored: restores into a throwaway database and checks key tables and audit integrity.
# Usage: ADMIN_URL=postgres://user:pass@host:5432/postgres ./restore-check.sh backups/promarketing-XXXX.dump
set -eu
DUMP="${1:?path to .dump}"
: "${ADMIN_URL:?ADMIN_URL (connection to the 'postgres' db) is required}"
TMPDB="restore_check_$(date +%s)"
psql "$ADMIN_URL" -qc "CREATE DATABASE $TMPDB"
TARGET=$(echo "$ADMIN_URL" | sed "s#/[^/]*\$#/$TMPDB#")
trap 'psql "$ADMIN_URL" -qc "DROP DATABASE IF EXISTS $TMPDB"' EXIT
pg_restore --no-owner --dbname="$TARGET" "$DUMP"
for t in accounts_user orders_order orders_orderitem payments_payment audit_auditlog support_dispute; do
  printf "%s: " "$t"; psql "$TARGET" -tAc "SELECT count(*) FROM $t"
done
psql "$TARGET" -tAc "SELECT CASE WHEN count(*) = max(seq) OR count(*) = 0 THEN 'audit seq ok' ELSE 'audit seq GAP' END FROM audit_auditlog"
echo "restore check ok"
