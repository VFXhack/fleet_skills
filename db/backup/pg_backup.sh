#!/usr/bin/env bash
# pg_backup.sh — nightly pg_dump of the fleet + mempalace DBs on mckenna.
# ADR 0025's backup prerequisite. Installed as a systemd USER timer (pg-backup.timer);
# a watts scheduled task pulls the dumps to E:\backups\mckenna_pg (second host).
#
# DSNs come from ~/.pg_backup_env (mode 600, NOT in git):
#   FLEET_DSN=postgresql://fleet:...@127.0.0.1:5432/fleet        (required)
#   MEMPALACE_DSN=postgresql://...@127.0.0.1:5432/mempalace      (optional until provided)
set -u
BACKUP_DIR="${BACKUP_DIR:-/mnt/shared/pg_backups}"
KEEP_DAYS="${KEEP_DAYS:-14}"
ENV_FILE="$HOME/.pg_backup_env"

[ -f "$ENV_FILE" ] || { echo "FATAL: $ENV_FILE missing"; exit 1; }
# shellcheck disable=SC1090
. "$ENV_FILE"
mkdir -p "$BACKUP_DIR"
stamp=$(date +%Y%m%d)
fail=0

dump() { # dump <name> <dsn>
    local name="$1" dsn="$2" out
    out="$BACKUP_DIR/${name}_${stamp}.dump"
    if pg_dump --format=custom --compress=6 --file="$out.part" "$dsn"; then
        mv "$out.part" "$out"
        echo "OK   $name -> $out ($(du -h "$out" | cut -f1))"
    else
        rm -f "$out.part"
        echo "FAIL $name pg_dump exited $?"
        fail=1
    fi
}

dump fleet "${FLEET_DSN:?FLEET_DSN not set in $ENV_FILE}"
if [ -n "${MEMPALACE_DSN:-}" ]; then
    dump mempalace "$MEMPALACE_DSN"
else
    echo "SKIP mempalace — MEMPALACE_DSN not set in $ENV_FILE (add it; ADR 0025 wants both)"
fi

find "$BACKUP_DIR" -name '*.dump' -mtime "+$KEEP_DAYS" -delete
echo "done $(date -Is); retained: $(ls "$BACKUP_DIR" | wc -l) files"
exit $fail
