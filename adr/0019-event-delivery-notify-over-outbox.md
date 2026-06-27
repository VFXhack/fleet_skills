# ADR 0019 — Event delivery: Postgres `LISTEN/NOTIFY` over a durable outbox (`events` table)

**Status:** Accepted
**Date:** 2026-06-26
**Refines:** ADR 0012 (thin Python worker on `LISTEN/NOTIFY`), 0013 (`VersionRecorded`),
0018 (`PublishRecorded`; the Roustabout's auto-publish + chain actions)

## Context
ADR 0012 sketched the Roustabout as a thin Python worker on Postgres `LISTEN/NOTIFY`, graduating to a real
workflow engine "when hand-rolled retries/observability earn it." ADR 0018 added a **second event**
(`PublishRecorded`) and gave the Roustabout **gate-crossing** (auto-publish) and **work-starting** (chains)
authority. Pure `NOTIFY` is **fire-and-forget**: a notification sent while the worker is down is **lost,
with no replay**. For a solo operator whose Roustabout will not always be running, a missed event means a
take with **no proxy**, or an asset **silently never auto-published**.

## Decision
**`LISTEN/NOTIFY` as a low-latency wakeup, backed by a durable `events` outbox table** (the transactional
outbox pattern):

- The **Submitter writes an `events` row** (`type`, `payload`, `status='pending'`) **in the same
  transaction** as the version/publish insert, then issues `NOTIFY`. The event is **durable the instant the
  row commits**; the `NOTIFY` is only a latency optimization, **never the source of truth**.
- The **Roustabout** consumes `pending` events (woken by `NOTIFY`, with a periodic **poll as a backstop**),
  runs the flow, and marks the row `done` (with error/attempt bookkeeping). **On startup it drains all
  `pending` rows** — nothing missed while it was down.
- **Delivery is at-least-once**, so **every Roustabout action is idempotent**: proxy / log / contact-sheet
  are overwrite-safe; **auto-publish and chains guard on "already done"** (e.g. a unique key on
  `(source_version → publish)` and `(trigger → chain)`) so re-processing can never double-publish or
  double-submit.
- **No new infrastructure** — it is still just the Postgres on **Mckenna** we already run.

Rejected: **pure `LISTEN/NOTIFY`** (0012's letter) — lossy, no replay, unacceptable for unattended
single-operator runs; an **external broker** (Redis / RabbitMQ / Temporal) — durability + retries +
observability out of the box, but **new Fleet infra**, premature per 0012's graduate-when-earned rule. The
outbox is the **minimal durable step that stays "just Postgres."**

## Consequences
- **Schema:** a new **`events`** table (migration `0003_events_outbox.sql`) —
  `id, type, payload jsonb, status, attempts, created_at, processed_at`. It lives in the provenance DB but
  is an **operational queue, not provenance** — kept distinct from the UL tables (`projects`, `runs`, …).
- The **Submitter** gains "write `events` row + `NOTIFY`" inside its existing version/publish-write
  transaction; the **Roustabout** gains a consume → mark → drain loop + **idempotency guards**.
- **Observability/retries are hand-rolled** in the worker; when that bookkeeping outgrows the table
  (dead-letter, backoff, fan-out to multiple consumers), **that** is the earned trigger to graduate to a
  real engine (ADR 0012) — and **this ADR is what gets reversed**.
- Both `VersionRecorded` and `PublishRecorded` travel this **one** path.

## Why an ADR
The transport for **every** orchestration event is load-bearing and reverses with real cost (schema +
rewiring both the Submitter and the Roustabout). It also picks **deliberately against the literal 0012
phrasing** (adds the outbox), so the reasoning is on record.
