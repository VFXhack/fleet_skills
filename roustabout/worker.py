"""Roustabout worker — the deterministic orchestration spine (ADR 0018 / 0019).

Receives orchestration events from the durable `events` outbox and runs the
pre-wired FLOWS (handlers.py). Transport is Postgres LISTEN/NOTIFY for low
latency, backed by the outbox table for durability: if this worker is down,
events accumulate as `pending` rows and are drained on the next startup —
nothing is lost (ADR 0019).

Run:    python -m roustabout.worker
Needs:  the 0003_events_outbox.sql migration applied, and a Fleet DB DSN
        (FLEET_DB_DSN env or ~/.fleet/config.toml [db].dsn — see db/README.md).
"""
from __future__ import annotations

import logging
import signal

import psycopg

from .config import EVENT_CHANNEL, resolve_dsn
from .handlers import Event, dispatch

log = logging.getLogger("roustabout")

POLL_TIMEOUT_SECONDS = 30   # backstop: re-drain even if a NOTIFY was missed
MAX_ATTEMPTS = 5            # park an event as 'error' after this many failures

# Oldest pending first; `seen` excludes rows already attempted THIS pass so a
# failing event is retried on the next wakeup, not hot-looped. SKIP LOCKED lets
# multiple workers share the queue safely.
_CLAIM_SQL = """
    SELECT id, type, subject_id, payload, attempts
    FROM events
    WHERE status = 'pending' AND NOT (id = ANY(%(seen)s::uuid[]))
    ORDER BY created_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1
"""


def drain_pending(conn: psycopg.Connection) -> int:
    """Claim and process every pending event once, oldest first; return #done.

    Each event is claimed with FOR UPDATE SKIP LOCKED inside a transaction, and
    the handler runs inside a SAVEPOINT so a handler failure rolls back its own
    writes without poisoning the bookkeeping UPDATE that records the failure.
    Failures bump `attempts` and re-queue ('pending') until MAX_ATTEMPTS, then
    park as 'error'.
    """
    done = 0
    seen: list = []
    while True:
        with conn.transaction():
            row = conn.execute(_CLAIM_SQL, {"seen": seen}).fetchone()
            if row is None:
                return done
            ev = Event(id=row[0], type=row[1], subject_id=row[2],
                       payload=row[3], attempts=row[4])
            seen.append(ev.id)
            try:
                with conn.transaction():        # savepoint around the handler
                    dispatch(ev, conn)
            except Exception as exc:            # noqa: BLE001 — park, never crash the loop
                attempts = ev.attempts + 1
                status = "error" if attempts >= MAX_ATTEMPTS else "pending"
                conn.execute(
                    "UPDATE events SET attempts = %s, last_error = %s, status = %s "
                    "WHERE id = %s",
                    (attempts, repr(exc), status, ev.id),
                )
                log.exception("event %s (%s) failed -> %s (attempt %d/%d)",
                              ev.id, ev.type, status, attempts, MAX_ATTEMPTS)
            else:
                conn.execute(
                    "UPDATE events SET status = 'done', processed_at = now() "
                    "WHERE id = %s",
                    (ev.id,),
                )
                done += 1


def run() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    dsn = resolve_dsn()

    # Dedicated autocommit connection for LISTEN; a separate one for claim/process.
    listen_conn = psycopg.connect(dsn, autocommit=True)
    listen_conn.execute(f"LISTEN {EVENT_CHANNEL}")
    work_conn = psycopg.connect(dsn)

    stop = False

    def _request_stop(*_):
        nonlocal stop
        stop = True
        log.info("shutdown requested")

    for sig_name in ("SIGINT", "SIGTERM"):           # SIGTERM may be absent on Windows
        sig = getattr(signal, sig_name, None)
        if sig is not None:
            try:
                signal.signal(sig, _request_stop)
            except (ValueError, OSError):
                pass

    log.info("roustabout up; draining backlog, then listening on '%s'", EVENT_CHANNEL)
    backlog = drain_pending(work_conn)               # startup drain — catch what we missed
    if backlog:
        log.info("drained %d backlog event(s)", backlog)

    while not stop:
        woken = False
        for _ in listen_conn.notifies(timeout=POLL_TIMEOUT_SECONDS, stop_after=1):
            woken = True
        if stop:
            break
        n = drain_pending(work_conn)
        if n:
            log.info("processed %d event(s)%s", n, "" if woken else " (poll backstop)")

    listen_conn.close()
    work_conn.close()
    log.info("roustabout stopped")


if __name__ == "__main__":
    run()
