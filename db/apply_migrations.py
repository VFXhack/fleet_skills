"""apply_migrations — apply migration files to the CONFIG DSN (prod-capable).

The deliberate prod counterpart of the fleet_test-only fixtures: it targets
whatever ~/.fleet/config.toml [db].dsn points at ($FLEET_DB_DSN overrides, so
it can drive a test DB too). Because that can be PROD, it:

  * prints the target dbname + host and each migration's status FIRST,
  * skips migrations already applied (probed by their marker relation/column),
  * writes NOTHING without --yes,
  * runs each file in its own transaction (the files carry BEGIN/COMMIT).

Usage (from the repo root, venv python):
  python -m db.apply_migrations                       # status only: what would apply
  python -m db.apply_migrations --yes                 # apply everything missing, in order
"""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path

import psycopg

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

# every known migration, in order, with the probe that says "already applied":
#   (filename, probe SQL returning a row iff applied)
LEDGER = (
    ("0001_initial_schema.sql",
     "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='projects'"),
    ("0002_run_spec.sql",
     "SELECT 1 FROM information_schema.columns WHERE table_name='runs' AND column_name='spec'"),
    ("0003_events_outbox.sql",
     "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='events'"),
    ("0004_sequences_and_look.sql",
     "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='sequences'"),
    ("0005_shot_overrides.sql",
     "SELECT 1 FROM pg_tables WHERE schemaname='public' AND tablename='shot_overrides'"),
)


def resolve_dsn() -> str:
    import os
    dsn = os.environ.get("FLEET_DB_DSN")
    if not dsn:
        cfg = Path.home() / ".fleet" / "config.toml"
        with cfg.open("rb") as fh:
            dsn = tomllib.load(fh)["db"]["dsn"]
    return dsn


def main() -> int:
    write = "--yes" in sys.argv[1:]
    dsn = resolve_dsn()
    info = psycopg.conninfo.conninfo_to_dict(dsn)
    print(f"target: dbname={info.get('dbname')!r} host={info.get('host', 'localhost')!r}")

    conn = psycopg.connect(dsn)
    try:
        pending = []
        for fname, probe in LEDGER:
            applied = conn.execute(probe).fetchone() is not None
            print(f"  {fname:<32} {'applied' if applied else 'MISSING'}")
            if not applied:
                pending.append(fname)

        if not pending:
            print("nothing to do — every known migration is applied.")
            return 0
        if not write:
            print(f"\nwould apply, in order: {', '.join(pending)}")
            print("re-run with --yes to apply.")
            return 0

        for fname in pending:
            sql = (MIGRATIONS_DIR / fname).read_text()
            conn.execute(sql)
            conn.commit()
            print(f"applied {fname}")
        print("done.")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
