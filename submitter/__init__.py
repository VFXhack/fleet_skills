"""Submitter — the connective tissue / sole writer of the pipeline (CONTEXT.md
→ *Submitter*; ADR 0010/0013/0018).

This package currently implements the **emit path** only: durable emission of the
orchestration events `VersionRecorded` / `PublishRecorded` into the `events`
outbox (events.py), plus a manual smoke tool (emit_demo.py). The rest of the
Submitter (ingest, run/version writes, dispatch, counter allocation) is not built
yet — see skills/submitter/SKILL.md for the full spec.
"""
