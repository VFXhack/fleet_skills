#!/usr/bin/env bash
# Fleet TEST database helper -- see db/README.md -> "Test database".
#
# Subcommands:
#   setup   create the fleet_test database (if absent) + apply all migrations
#   reset   TRUNCATE every table back to empty (the fast, blunt teardown)
#   info    print row counts per table
#   dsn     print the resolved test DSN (for `export FLEET_DB_DSN=$(... dsn)`)
#   psql    drop into psql against fleet_test (extra args are passed through)
#
# DSN resolution (no secrets in git): $FLEET_TEST_DSN if set, else the prod
# [db].dsn from ~/.fleet/config.toml with the database name swapped to
# `fleet_test`. Run this where psql can reach the DB (on Mckenna, or any box with
# psql + tailnet). Tools (create-project, submitter) point at the test DB by
# `export FLEET_DB_DSN="$(bash db/test_db.sh dsn)"`.
#
# SAFETY: every destructive op asserts the resolved DSN targets `fleet_test`, so
# this can never truncate or re-create prod.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIGRATIONS="$HERE/migrations"
RESET_SQL="$HERE/reset_test.sql"
TEST_DB="fleet_test"

_dsn_value_from_config() {
  local cfg="$HOME/.fleet/config.toml"
  [[ -f "$cfg" ]] || { echo "error: no \$FLEET_TEST_DSN and no $cfg" >&2; exit 1; }
  grep -E '^[[:space:]]*dsn[[:space:]]*=' "$cfg" | head -1 | sed -E 's/^[^"]*"//; s/".*$//'
}

# Swap the database name in a DSN (handles both `dbname=fleet` and URL `/fleet`).
_swap_db() {
  local dsn="$1" db="$2"
  if [[ "$dsn" == *"dbname="* ]]; then
    sed -E "s/dbname=fleet([^_a-zA-Z]|\$)/dbname=$db\1/" <<<"$dsn"
  else
    sed -E "s#/fleet(\?|\$)#/$db\1#" <<<"$dsn"
  fi
}

resolve_test_dsn() {
  if [[ -n "${FLEET_TEST_DSN:-}" ]]; then printf '%s' "$FLEET_TEST_DSN"; return; fi
  _swap_db "$(_dsn_value_from_config)" "$TEST_DB"
}

resolve_admin_dsn() {  # the prod/maintenance DB, used only to CREATE DATABASE
  _dsn_value_from_config
}

assert_test() {
  local dsn="$1"
  if [[ "$dsn" != *"$TEST_DB"* ]]; then
    echo "REFUSING: resolved DSN does not target $TEST_DB:" >&2
    echo "  $dsn" >&2
    exit 1
  fi
}

cmd_dsn()  { resolve_test_dsn; echo; }
cmd_psql() { exec psql "$(resolve_test_dsn)" "$@"; }

cmd_info() {
  psql "$(resolve_test_dsn)" -P pager=off -c "
    SELECT 'projects' AS tbl, count(*) FROM projects
    UNION ALL SELECT 'runs', count(*) FROM runs
    UNION ALL SELECT 'versions', count(*) FROM versions
    UNION ALL SELECT 'publishes', count(*) FROM publishes
    UNION ALL SELECT 'deliveries', count(*) FROM deliveries
    UNION ALL SELECT 'assets', count(*) FROM assets
    UNION ALL SELECT 'bindings', count(*) FROM bindings
    UNION ALL SELECT 'events', count(*) FROM events ORDER BY 1;"
}

cmd_reset() {
  local dsn; dsn="$(resolve_test_dsn)"
  assert_test "$dsn"
  psql "$dsn" -P pager=off -v ON_ERROR_STOP=1 -f "$RESET_SQL"
  echo "reset OK -- $TEST_DB truncated."
}

cmd_setup() {
  local admin test_dsn; admin="$(resolve_admin_dsn)"; test_dsn="$(resolve_test_dsn)"
  assert_test "$test_dsn"
  # create the DB if it isn't there yet (CREATE DATABASE can't run in a txn)
  if ! psql "$admin" -tAc "SELECT 1 FROM pg_database WHERE datname='$TEST_DB'" | grep -q 1; then
    psql "$admin" -c "CREATE DATABASE $TEST_DB OWNER fleet"
  else
    echo "$TEST_DB already exists -- (re)applying migrations is idempotent only if they are."
  fi
  for f in "$MIGRATIONS"/*.sql; do
    echo ">>> $f"
    psql "$test_dsn" -P pager=off -v ON_ERROR_STOP=1 -q -f "$f"
  done
  echo "setup OK."
}

case "${1:-}" in
  setup) shift; cmd_setup "$@" ;;
  reset) shift; cmd_reset "$@" ;;
  info)  shift; cmd_info  "$@" ;;
  dsn)   shift; cmd_dsn   "$@" ;;
  psql)  shift; cmd_psql  "$@" ;;
  *) echo "usage: $0 {setup|reset|info|dsn|psql}" >&2; exit 2 ;;
esac
