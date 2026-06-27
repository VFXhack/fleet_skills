"""The Submitter's EMIT PATH — durable orchestration-event emission (ADR 0018/0019).

The Submitter is the SOLE event emitter. In the SAME transaction as the
version/publish write it describes, it appends a row to the `events` outbox and
issues a NOTIFY. The row is the durable source of truth; the NOTIFY is only a
low-latency wakeup that may be missed (the Roustabout drains the outbox anyway).

Call these INSIDE the caller's open transaction (do NOT commit here) so the event
and the row it describes commit atomically — the whole point of the outbox:

    with conn.transaction():
        conn.execute("UPDATE versions SET address=%s WHERE id=%s", (addr, vid))
        emit_version_recorded(conn, vid)              # same txn -> atomic

    with conn.transaction():
        pid = ...  # INSERT INTO publishes (...) RETURNING id
        emit_publish_recorded(conn, pid, role="Hero")

Emission is idempotent: `events` has UNIQUE(type, subject_id) and we INSERT
ON CONFLICT DO NOTHING, so a retried emit is a harmless no-op.
"""
from __future__ import annotations

import psycopg
from psycopg.types.json import Json

from .config import EVENT_CHANNEL


def _emit(conn: psycopg.Connection, type_: str, subject_id, payload: dict) -> None:
    conn.execute(
        "INSERT INTO events (type, subject_id, payload) VALUES (%s, %s, %s) "
        "ON CONFLICT (type, subject_id) DO NOTHING",
        (type_, subject_id, Json(payload)),
    )
    # pg_notify() takes channel + payload as VALUES (NOTIFY's identifier form
    # can't be parameterized). Transactional: listeners receive it on COMMIT.
    conn.execute("SELECT pg_notify(%s, %s)", (EVENT_CHANNEL, str(subject_id)))


def emit_version_recorded(conn: psycopg.Connection, version_id, extra: dict | None = None) -> None:
    """Emit `VersionRecorded` for a landed take.

    Enriches the payload with run context (run_id, shot_code, run_type) so the
    Roustabout can dispatch without re-querying. Call after the version's address
    is written, in the same transaction (ADR 0013).
    """
    row = conn.execute(
        "SELECT v.run_id, v.shot_code, r.type "
        "FROM versions v JOIN runs r ON r.id = v.run_id "
        "WHERE v.id = %s",
        (version_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"emit_version_recorded: no version {version_id!r}")
    run_id, shot_code, run_type = row
    payload = {"run_id": str(run_id), "shot_code": shot_code, "run_type": run_type}
    if extra:
        payload.update(extra)
    _emit(conn, "VersionRecorded", version_id, payload)


def emit_publish_recorded(
    conn: psycopg.Connection, publish_id, role: str | None = None, extra: dict | None = None
) -> None:
    """Emit `PublishRecorded` for a new publish (Roustabout auto-publish OR a human
    promote).

    `role`/tag is what the Roustabout's chain registry matches on (ADR 0018); pass
    it from the promote call. (Publishes carry no role column yet — a deferred
    schema item; until then the caller supplies it.)
    """
    row = conn.execute(
        "SELECT p.shot_code, p.source_version_id, r.type "
        "FROM publishes p "
        "JOIN versions v ON v.id = p.source_version_id "
        "JOIN runs r ON r.id = v.run_id "
        "WHERE p.id = %s",
        (publish_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"emit_publish_recorded: no publish {publish_id!r}")
    shot_code, source_version_id, run_type = row
    payload = {
        "shot_code": shot_code,
        "source_version_id": str(source_version_id),
        "run_type": run_type,
    }
    if role:
        payload["role"] = role
    if extra:
        payload.update(extra)
    _emit(conn, "PublishRecorded", publish_id, payload)
