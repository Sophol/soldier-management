#!/bin/bash
# Daily backup of the database and the uploaded files (photos, attachments), run by the "backup" service of
# docker-compose.yml. Every day at BACKUP_TIME:
#   - the database  -> $BACKUP_DIR/db/sm-YYYY-MM-DD_HHMM.sql.gz   (copies older than BACKUP_KEEP_DAYS are removed)
#   - the files     -> $BACKUP_DIR/storage/                      (a copy kept up to date: only new files are copied)
# Run one at once:  docker compose run --rm backup now
# Restore:          gunzip < backups/db/sm-....sql.gz | docker compose exec -T db sh -c 'mysql -uroot -p"$MYSQL_ROOT_PASSWORD" soldier-management'
set -uo pipefail

: "${MYSQL_HOST:=db}" "${MYSQL_DATABASE:=soldier-management}" "${BACKUP_TIME:=01:00}" "${BACKUP_KEEP_DAYS:=14}"
export MYSQL_PWD="${MYSQL_ROOT_PASSWORD:?MYSQL_ROOT_PASSWORD is not set}"  # not on the command line (ps)
OUT=/backups

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') backup: $*"; }

backup_now() {
    mkdir -p "$OUT/db" "$OUT/storage"
    local stamp file part
    stamp=$(date +%Y-%m-%d_%H%M)
    file="$OUT/db/sm-$stamp.sql.gz"
    part="$OUT/db/.sm-$stamp.sql.gz.part"
    log "database -> $file"
    # --single-transaction: a consistent copy while the system is in use, without locking the tables
    if mysqldump -h "$MYSQL_HOST" -uroot --single-transaction --quick --routines --triggers --no-tablespaces \
            --default-character-set=utf8mb4 "$MYSQL_DATABASE" | gzip -6 > "$part"; then
        mv "$part" "$file"
        log "database done ($(du -h "$file" | cut -f1))"
    else
        rm -f "$part"
        log "ERROR: the database backup failed"
        return 1
    fi
    if [ -d /storage ]; then
        cp -a -u /storage/. "$OUT/storage/" && log "files done" || log "ERROR: copying the files failed"
    fi
    find "$OUT/db" -name 'sm-*.sql.gz' -mtime +"$BACKUP_KEEP_DAYS" -print -delete | sed 's/^/removed old backup: /'
}

seconds_until_next() {
    local now target
    now=$(date +%s)
    target=$(date -d "today $BACKUP_TIME" +%s)
    [ "$target" -le "$now" ] && target=$(date -d "tomorrow $BACKUP_TIME" +%s)
    echo $((target - now))
}

if [ "${1:-}" = "now" ]; then
    backup_now
    exit $?
fi

log "daily at $BACKUP_TIME ($(date +%Z)), keeping $BACKUP_KEEP_DAYS days, into $OUT"
# no backup yet today (first start, or the machine was off at BACKUP_TIME): one now, once the database is up
if ! ls "$OUT/db/sm-$(date +%Y-%m-%d)_"*.sql.gz >/dev/null 2>&1; then
    for _ in $(seq 60); do mysqladmin -h "$MYSQL_HOST" -uroot ping --silent >/dev/null 2>&1 && break; sleep 5; done
    backup_now
fi
while true; do
    sleep "$(seconds_until_next)"
    backup_now
    sleep 60
done
