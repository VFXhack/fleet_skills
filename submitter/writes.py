"""Submitter WRITE PATH — the operations that write a provenance row and emit its
event in ONE transaction (ADR 0008 / 0013 / 0018). They CALL the emit path
(events.py).

Unlike the txn-agnostic emit_* functions, these OWN their transaction; emit runs
inside it so the row and its event commit atomically (transactional outbox).
Counters are allocated by the WRITER here, never by a DB trigger (ADR 0008).
"""
from __future__ import annotations

import psycopg

from .events import emit_publish_recorded, emit_version_recorded


def record_landed_take(conn: psycopg.Connection, version_id, address: str) -> None:
    """Render completed: write the take's output `address`, then emit
    `VersionRecorded` — so the event means *a finished, addressable take exists*,
    never *a render was requested* (ADR 0013).

    Idempotent: re-running re-sets the same address (harmless) and the emit is
    ON CONFLICT DO NOTHING, so no duplicate event.
    """
    with conn.transaction():
        affected = conn.execute(
            "UPDATE versions SET address = %s WHERE id = %s",
            (address, version_id),
        ).rowcount
        if affected == 0:
            raise ValueError(f"record_landed_take: no version {version_id!r}")
        emit_version_recorded(conn, version_id)


def promote(conn: psycopg.Connection, version_id, path: str | None = None,
            role: str | None = None) -> tuple:
    """Internal gate: promote a Version to a Publish — a human supervisor gate OR
    the Roustabout's auto-publish (ADR 0018). Allocates the next per-shot `p###`
    (writer-allocated, ADR 0008), inserts the publish, then emits
    `PublishRecorded`. Returns ``(publish_id, number)``.

    Concurrency: a per-shot advisory lock serializes counter allocation so two
    promotes for the same shot can't collide on UNIQUE(shot_code, number); it
    releases at transaction end.
    """
    with conn.transaction():
        row = conn.execute(
            "SELECT shot_code FROM versions WHERE id = %s", (version_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"promote: no version {version_id!r}")
        shot_code = row[0]

        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s)::bigint)", (shot_code,))
        number = conn.execute(
            "SELECT COALESCE(MAX(number), 0) + 1 FROM publishes WHERE shot_code = %s",
            (shot_code,),
        ).fetchone()[0]

        publish_id = conn.execute(
            "INSERT INTO publishes (source_version_id, shot_code, number, path) "
            "VALUES (%s, %s, %s, %s) RETURNING id",
            (version_id, shot_code, number, path),
        ).fetchone()[0]

        emit_publish_recorded(conn, publish_id, role=role)

    return publish_id, number
