"""Submitter WRITE PATH — the operations that write a provenance row and emit its
event in ONE transaction (ADR 0008 / 0013 / 0018). They CALL the emit path
(events.py).

Unlike the txn-agnostic emit_* functions, these OWN their transaction; emit runs
inside it so the row and its event commit atomically (transactional outbox).
Counters are allocated by the WRITER here, never by a DB trigger (ADR 0008).
"""
from __future__ import annotations

import psycopg
from psycopg.types.json import Json

from .events import emit_publish_recorded, emit_version_recorded
from .expand import VersionSeed


def write_versions(conn: psycopg.Connection, run_id, seeds: list[VersionSeed]) -> list[tuple]:
    """Expand-write: INSERT one `versions` row per VersionSeed for `run_id`,
    allocating the per-Shot `v###` counter (writer-allocated, ADR 0008 — like
    `promote` does for `p###`). `address` stays NULL — no take has landed yet
    (ADR 0013); `record_landed_take` fills it and emits `VersionRecorded` later.

    Returns [(version_id, number), …] in seed order. One transaction: either all
    Versions for the Run land or none do. NOT idempotent — call once per Run
    generation (a re-expand would allocate a fresh block of numbers). Guards
    against double-expand by refusing a Run that already has Versions.

    Concurrency: a per-shot advisory lock serializes counter allocation so two
    expands for the same Shot can't collide on UNIQUE(shot_code, number).
    """
    with conn.transaction():
        row = conn.execute(
            "SELECT shot_code FROM runs WHERE id = %s", (run_id,)
        ).fetchone()
        if row is None:
            raise ValueError(f"write_versions: no run {run_id!r}")
        shot_code = row[0]

        already = conn.execute(
            "SELECT count(*) FROM versions WHERE run_id = %s", (run_id,)
        ).fetchone()[0]
        if already:
            raise ValueError(
                f"write_versions: run {run_id!r} already has {already} version(s) "
                f"- expand runs once per generation, it does not top up")

        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s)::bigint)", (shot_code,))
        base = conn.execute(
            "SELECT COALESCE(MAX(number), 0) FROM versions WHERE shot_code = %s",
            (shot_code,),
        ).fetchone()[0]

        out = []
        for i, seed in enumerate(seeds, start=1):
            number = base + i
            version_id = conn.execute(
                "INSERT INTO versions (run_id, shot_code, number, stage, delta, "
                "frozen_submission) VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                (run_id, shot_code, number, seed.stage,
                 Json(seed.delta), Json(seed.frozen_submission)),
            ).fetchone()[0]
            out.append((version_id, number))
    return out


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
