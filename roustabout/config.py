"""Fleet DB DSN resolution + shared event-channel contract.

DSN resolution order matches `db/README.md` (the same order create-project, the
Submitter, and runners use):
    1. FLEET_DB_DSN environment variable, else
    2. ~/.fleet/config.toml -> [db].dsn   (per-machine, never committed)
"""
from __future__ import annotations

import os
import tomllib  # stdlib, Python 3.11+
from pathlib import Path

# The Postgres NOTIFY channel both the Submitter and the Roustabout use. Shared
# contract — see db/migrations/0003_events_outbox.sql.
EVENT_CHANNEL = "fleet_events"


def resolve_dsn() -> str:
    """Return the Fleet provenance-DB DSN, or raise if none is configured."""
    dsn = os.environ.get("FLEET_DB_DSN")
    if dsn:
        return dsn

    cfg = Path.home() / ".fleet" / "config.toml"
    if cfg.is_file():
        with cfg.open("rb") as fh:
            data = tomllib.load(fh)
        dsn = (data.get("db") or {}).get("dsn")
        if dsn:
            return dsn

    raise RuntimeError(
        "No Fleet DB DSN found. Set FLEET_DB_DSN, or add [db].dsn to "
        "~/.fleet/config.toml (see db/README.md)."
    )
