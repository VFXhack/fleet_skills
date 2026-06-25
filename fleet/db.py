"""Connection helper for the Fleet provenance core (Postgres on Mckenna, ADR 0008)."""

from __future__ import annotations

import psycopg

from . import config


def connect(dsn: str | None = None) -> psycopg.Connection:
    """Open a connection to the provenance DB.

    The connection is NOT autocommit — the caller owns the transaction and must
    commit() or rollback(). DSN defaults to the resolved Fleet config.
    """
    return psycopg.connect(dsn or config.get_dsn())
