"""Roustabout FLOWS — the deterministic reactions wired to each event (ADR 0018).

The worker (worker.py) owns the SPINE: receive -> claim -> dispatch -> mark. This
module owns DISPATCH + the handlers. Per ADR 0018 the Roustabout is rule-based,
no LLM, no judgment: if a step would need to *judge*, it belongs up in the
Ringmaster, not here.

REALITY CHECK (first cut): the DECISIONS are real — the run-completion barrier and
the auto-publish eligibility test are pure / DB logic. The SIDE EFFECTS that touch
pieces we haven't built yet are stubbed and clearly marked:
  * proxy/thumbnail + contact-sheet -> need render/image tooling on Huxley.
  * auto-publish WRITE + chains -> must go THROUGH the Submitter (the sole writer,
    which allocates p### and emits PublishRecorded); the Submitter isn't built yet.
    We log intent and do NOT write the publish directly (that would bypass the
    writer and skip the PublishRecorded event).
  * notify -> the channel (Notion view / a feed) is a deferred config choice.
Each stub logs exactly what it WOULD do, so the spine is observable end-to-end now.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import psycopg

log = logging.getLogger("roustabout.flows")

# Run types whose single deterministic output the Roustabout may auto-publish
# (ADR 0018): there is no take to CHOOSE, so promoting it is mechanical, not
# judgment. Creative sweep-shapes (seed-sweep/prompt-variation/xy-plot/refine)
# are deliberately absent.
AUTO_PUBLISH_TYPES = {"control-pass", "upscale", "comp"}


@dataclass
class Event:
    """One row claimed from the `events` outbox."""
    id: Any
    type: str
    subject_id: Any
    payload: dict
    attempts: int


# ---------------------------------------------------------------------------
# dispatch — the spine calls this once per claimed event
# ---------------------------------------------------------------------------
def dispatch(ev: Event, conn: psycopg.Connection) -> None:
    if ev.type == "VersionRecorded":
        on_version_recorded(ev, conn)
    elif ev.type == "PublishRecorded":
        on_publish_recorded(ev, conn)
    else:
        log.warning("unknown event type %r (id=%s) — ignoring", ev.type, ev.id)


# ---------------------------------------------------------------------------
# VersionRecorded — a take landed (its address is written; ADR 0013). Per-take
# reactions, then the per-run completion barrier (ADR 0018).
# ---------------------------------------------------------------------------
def on_version_recorded(ev: Event, conn: psycopg.Connection) -> None:
    version_id = ev.subject_id
    run_id = ev.payload.get("run_id")

    # --- per-take: fires for every landed take ---
    _log_take(version_id, ev.payload)          # real: a structured log line
    _render_proxy(version_id, ev.payload)      # stub: render tooling on Huxley

    # --- per-run barrier: only once ALL of this run's takes have landed ---
    if run_id and _run_complete(run_id, conn):
        on_run_complete(run_id, conn)


def _run_complete(run_id: Any, conn: psycopg.Connection) -> bool:
    """True iff every version of the run has landed (address written).

    Deterministic, not a judgment (ADR 0018): all N versions are inserted at
    submit time with address NULL, so the run is complete exactly when none
    remain NULL — a count the Roustabout READS, never decides.
    """
    total, pending = conn.execute(
        "SELECT count(*) AS total, "
        "       count(*) FILTER (WHERE address IS NULL) AS pending "
        "FROM versions WHERE run_id = %s",
        (run_id,),
    ).fetchone()
    return total > 0 and pending == 0


def on_run_complete(run_id: Any, conn: psycopg.Connection) -> None:
    """Per-run actions, fired once the barrier is met.

    Idempotency (ADR 0019): this may re-run if its triggering event is
    reprocessed. The auto-publish WRITE will be guarded by publishes
    UNIQUE(shot_code, number) once the Submitter performs it; contact-sheet is
    overwrite-safe; notify needs a per-run de-dupe key when it becomes real.
    """
    run_type, version_count = _run_type_and_count(run_id, conn)
    log.info("run %s complete: type=%s versions=%d", run_id, run_type, version_count)

    if version_count > 1:
        _build_contact_sheet(run_id, run_type)        # stub: image tooling
    _notify_run_done(run_id, run_type, version_count)  # stub: notify channel TBD

    if _auto_publishable(run_type, version_count):
        _auto_publish(run_id, run_type, conn)          # stub: via the Submitter


def _run_type_and_count(run_id: Any, conn: psycopg.Connection) -> tuple[str, int]:
    run_type = conn.execute(
        "SELECT type FROM runs WHERE id = %s", (run_id,)
    ).fetchone()[0]
    version_count = conn.execute(
        "SELECT count(*) FROM versions WHERE run_id = %s", (run_id,)
    ).fetchone()[0]
    return run_type, version_count


def _auto_publishable(run_type: str, version_count: int) -> bool:
    """ADR 0018: cross Version->Publish only where there is nothing to choose —
    an operation type with exactly one deterministic output."""
    return run_type in AUTO_PUBLISH_TYPES and version_count == 1


# ---------------------------------------------------------------------------
# PublishRecorded — a publish was born (Roustabout auto-publish OR a human
# promote). Fires wired, judgment-free chains matched on Role/tag (ADR 0018).
# ---------------------------------------------------------------------------
def on_publish_recorded(ev: Event, conn: psycopg.Connection) -> None:
    key = ev.payload.get("role") or ev.payload.get("tag")
    chain = CHAINS.get(key)
    if chain is None:
        log.debug("publish %s (role/tag=%r): no wired chain", ev.subject_id, key)
        return
    _submit_chain(chain, ev, conn)             # stub: via the Submitter


# The chain registry: a SHORT, EXPLICIT map of (Publish Role/tag) -> a fully
# pinned follow-on Run recipe. Judgment-free by construction (default Spell,
# fixed params); the moment a "default" stops being obvious it graduates up to
# the Ringmaster (ADR 0018). First intended entry (deferred until the Submitter +
# the pinned depth Spell exist):
#   "Hero": {"run_type": "control-pass", "method": "<pinned default depth spell>"}
CHAINS: dict[str, dict] = {}


# ===========================================================================
# STUBS — real side effects land here as their dependencies get built.
# ===========================================================================
def _log_take(version_id: Any, payload: dict) -> None:
    log.info("take landed: version=%s shot=%s run_type=%s",
             version_id, payload.get("shot_code"), payload.get("run_type"))


def _render_proxy(version_id: Any, payload: dict) -> None:
    log.info("[stub] render proxy/thumbnail for version=%s "
             "(needs Huxley render tooling)", version_id)


def _build_contact_sheet(run_id: Any, run_type: str) -> None:
    log.info("[stub] build contact sheet for run=%s type=%s (needs image tooling)",
             run_id, run_type)


def _notify_run_done(run_id: Any, run_type: str, version_count: int) -> None:
    log.info("[stub] notify 'run done' run=%s type=%s versions=%d "
             "(notify channel TBD)", run_id, run_type, version_count)


def _auto_publish(run_id: Any, run_type: str, conn: psycopg.Connection) -> None:
    # ADR 0018: this MUST go through the Submitter (the sole writer; it allocates
    # the p### counter and emits PublishRecorded). Writing the publish here would
    # bypass the writer and skip the event — so we only log intent for now.
    log.info("[stub] auto-publish run=%s (type=%s) via the Submitter "
             "(Submitter not built yet)", run_id, run_type)


def _submit_chain(chain: dict, ev: Event, conn: psycopg.Connection) -> None:
    log.info("[stub] submit wired chain %r off publish=%s via the Submitter "
             "(Submitter/registry not built yet)", chain, ev.subject_id)
