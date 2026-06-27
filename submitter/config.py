"""Fleet DB DSN resolution + shared event-channel contract (Submitter copy).

Same resolution order as db/README.md (FLEET_DB_DSN, then ~/.fleet/config.toml).
Deliberately duplicated from roustabout/config.py to keep the Submitter decoupled
from the Roustabout; fold both into a shared `fleet` config module when a third
consumer (create-project, runners) needs it — see HANDOFF.
"""
from __future__ import annotations

import os
import tomllib  # stdlib, Python 3.11+
from pathlib import Path

# MUST match db/migrations/0003_events_outbox.sql and roustabout/config.py.
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
