# Roustabout

The **deterministic floor of orchestration** (CONTEXT.md → *Roustabout*; ADR 0012 / 0018 / 0019).
A thin Python worker that reacts to orchestration **events** and runs **pre-wired flows** —
rule-based, **no LLM, no judgment**. Judgment belongs up in the *Ringmaster* (deferred).

## The spine (worker.py) — what it does
1. **Connect** to the provenance DB (DSN via `FLEET_DB_DSN` or `~/.fleet/config.toml`; see `db/README.md`).
2. **Listen** on the `fleet_events` channel (`LISTEN/NOTIFY`) with a 30s **poll backstop**.
3. **Drain** the durable `events` outbox — `pending` rows, oldest first, claimed with
   `FOR UPDATE SKIP LOCKED`.
4. **Dispatch** by type: `VersionRecorded` → per-take + per-run reactions; `PublishRecorded` → wired chains.
5. **Mark** done / retry (`attempts`, then park as `error`) — at-least-once, idempotent handlers.
6. **Recover**: on startup it drains the backlog first, so nothing is lost while it was down (ADR 0019).

## FLOWS (handlers.py) — real vs stubbed (first cut)
| Handler | Status |
|---|---|
| run-completion barrier ("N of N landed") | **real** (a DB count) |
| auto-publish *eligibility* (`type ∈ {control-pass, upscale, comp} ∧ count == 1`) | **real** |
| structured take log | real |
| proxy/thumbnail, contact-sheet, notify | **stub** — render/image tooling; notify channel |
| auto-publish *write*, wired chains | **stub** — must go through the **Submitter** (not built yet) |

Each stub logs exactly what it *would* do, so the spine is observable end-to-end today.

## Event contract (with the Submitter)
The **Submitter** is the sole emitter (ADR 0018). In the **same transaction** as a version/publish write:
```sql
INSERT INTO events (type, subject_id, payload)
VALUES (:type, :subject_id, :payload)
ON CONFLICT (type, subject_id) DO NOTHING;     -- emission idempotency
NOTIFY fleet_events;                            -- low-latency wakeup (hint only)
```
- `type ∈ {VersionRecorded, PublishRecorded}`
- `subject_id` = the `versions.id` (VersionRecorded) / `publishes.id` (PublishRecorded)
- `payload` = dispatch context: `run_id`, `shot_code`, `run_type`, `role`/`tag`, …

See `db/migrations/0003_events_outbox.sql`.

## Run
```bash
pip install -r roustabout/requirements.txt
# apply the migration once (from Mckenna; see db/README.md):
#   sudo -u postgres psql -d fleet < db/migrations/0003_events_outbox.sql
python -m roustabout.worker          # from the repo root
```

## Status
Spine + decision logic: **implemented**. Side-effecting handlers: **stubbed** pending the Submitter,
render/image tooling, and the notify-channel choice. Next: the Submitter (so auto-publish + chains go
live), then the first wired chain (Hero → depth `control-pass`). See CONTEXT.md open-Qs and HANDOFF.md.
