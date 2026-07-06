"""Submitter — the connective tissue / sole writer of the pipeline (CONTEXT.md
→ *Submitter*; ADR 0010/0013/0018).

Built so far:
  * **emit path** — durable emission of `VersionRecorded` / `PublishRecorded` into
    the `events` outbox (events.py) + a manual smoke tool (emit_demo.py).
  * **write path** — `record_landed_take` / `promote` (writes.py), and `write_versions`
    (per-Shot `v###` allocation).
  * **submit / expand** — `submit <run_id>` (submit.py) loads an authored Run, checks
    the validation stamp (seam), and expands its `spec` into Versions (expand.py, the
    pure per-type expander; ADR 0016). Single responsibility, ADR 0024.
  * **dispatch (DRY)** — `dispatch <run_id>` (dispatch.py) translates each Version into
    the concrete Runner request it would send (proto-Template adapter); no spend yet.

Not built: real dispatch execution (call Runner -> download -> record_landed_take),
the validation gate + Template store, and authoring-side spec threading. See HANDOFF.
"""
