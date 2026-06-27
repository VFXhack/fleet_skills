# Submitter

The connective tissue and **sole writer** of the pipeline (CONTEXT.md → *Submitter*; ADR 0010/0013/0018).
Full spec: `skills/submitter/SKILL.md`. **This package is the first slice: the event emit path.**

## Emit path (events.py) — what's here
The Submitter is the only thing that emits orchestration events. Both are written as durable rows in the
`events` outbox **inside the same transaction** as the version/publish write they describe, then `NOTIFY`-ed
(ADR 0019 — transactional outbox):

| Function | Emits | Call it… |
|---|---|---|
| `emit_version_recorded(conn, version_id)` | `VersionRecorded` | right after writing `versions.address` on render completion (ADR 0013) |
| `emit_publish_recorded(conn, publish_id, role=…)` | `PublishRecorded` | right after `INSERT INTO publishes …` (auto-publish or human promote) |

Both **enrich the payload** (via a join) with the dispatch context the Roustabout needs — `run_id`,
`shot_code`, `run_type`, and (for publishes) the `role`/tag the chain registry matches on. Emission is
**idempotent**: `events` has `UNIQUE(type, subject_id)` and we `INSERT … ON CONFLICT DO NOTHING`.

```python
with conn.transaction():                                   # one txn = atomic with the event
    conn.execute("UPDATE versions SET address=%s WHERE id=%s", (addr, vid))
    emit_version_recorded(conn, vid)
```

## Smoke-test the spine end-to-end (emit_demo.py)
Before the full Submitter exists, light up the Roustabout against a real row:
```bash
python -m roustabout.worker          # terminal 1 (LISTENing)
python -m submitter.emit_demo version <versions.id>          # terminal 2
python -m submitter.emit_demo publish <publishes.id> --role Hero
```
The worker should drain it immediately and log the per-take / barrier / eligibility / chain-match flow
(with the stub handlers). Needs migrations `0001`–`0003` applied and a Fleet DSN (see `db/README.md`).

## Not built yet (next slices)
- The **write path** that *calls* these: `record_landed_take` (UPDATE address + emit) and `promote`
  (allocate `p###`, INSERT publish + emit). These need the Submitter's counter allocation (ADR 0008).
- Ingest, spec expansion → versions, dispatch to Flamenco/Runner (the rest of `SKILL.md`).
- Persisting a publish **tag/role** (e.g. `Hero`) so chains can match without the caller passing it.
