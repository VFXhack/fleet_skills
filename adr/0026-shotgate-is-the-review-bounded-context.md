# ADR 0026 — Shotgate is the review bounded context; the Roustabout's human-facing duties move into it

**Status:** Accepted
**Date:** 2026-08-19 (Session R2; drafted R1; contract grilled with Andy 2026-08-19)
**Amends:** ADR 0012, ADR 0018 · **Refines:** ADR 0019, ADR 0022

## Context
ADR 0018 gave the Roustabout contact-sheet assembly and notify duties. Since July,
**shotgate** (watts :8377, fleet-wide) became the production review surface — boards,
watchers, verdicts — and was promoted as THE review server. Running both means two
review surfaces and two event models. Shotgate's production failure modes (duplicate
boards per folder, watchers dying silently on idle timeout, server flake) are precisely
the problems ADR 0019's durable outbox was designed against.

Today's verdict contract is thin: `resolve()` writes `shotgate_resolution.<id>.json`
(absolute keep/reject/winner paths) next to the media and fires an optional `on_resolve`
hook; nothing else consumes it. Notes sit in board state, read ad hoc. Scores drive
keep/reject counts, then go nowhere. Shotgate and the fleet DB have no relationship.
Andy's four hardening questions (brief, R2 agenda) are answered here.

## Decision

### Boundary
- **Shotgate is the review bounded context.** It owns boards, contact sheets, watchers,
  human verdicts, and review notifications.
- **The Roustabout sheds its human-facing tier:** it keeps per-take ledger reactions
  (proxy/thumbnail, structured log), the per-run completion barrier, bounded
  auto-publish, and wired chains. On barrier completion it **notifies shotgate** to
  build/refresh the run's board instead of assembling a contact sheet itself.

### The verdict contract (grill Q1)
- A verdict writes a **`verdicts` row in the fleet DB** (version_id, verdict, score,
  note, board reference, decided_at). The DB is the record (R-3); the resolution JSON
  sidecar survives as a file-local convenience only.
- **keep/winner synchronously calls the Submitter's `promote()`** → `publishes` row
  (p###) + stable path + `PublishRecorded`. The verdict IS the human Publish gate
  (R-5's one promote seam, and the Hoist anchor per ADR 0022).
- **reject** = verdict row only; no publish.
- **A zero-keep resolution is legal.** A board may resolve "all failed": every item
  rejected, no promote, the gate stays closed until a better round. (Today shotgate
  forces ≥1 selection — removing that is a hardening item.) The round outcome is
  recorded on the board-resolution row so round N+1 knows it follows a failed round.
- **Downstream entitlement:** downstream may consume only publishes; every publish
  traces to a verdict or to an R-5 boardless auto-publish. A verdict without a promote
  has no downstream meaning.

### Notes (grill Q2)
- Per-item notes live on the **verdict row**; the per-board note lives on the
  **board-resolution row** (the round's summary, including why a zero-keep round
  failed).
- Round N+1 authoring (Cast, or Claude building a re-run) reads them via one
  deterministic query — "latest round's notes for this shot." Runs stay immutable;
  nothing is copied forward until authoring time.

### Grades (grill Q3)
- Scores land structured in the verdict row so history is queryable per
  shot/run/recipe, but **phase 1 wires no automated consumer** — they remain human
  shorthand driving the board's own keep/winner mechanics.
- Future uses (seed picks, training-pair curation, recipe A/B stats) are read-only
  queries over verdict history, each added as an explicit feature with its own
  decision. Scores are **never a hidden input to dispatch**.

### Shotgate ↔ fleet DB (grill Q4)
- **Shotgate becomes a first-class fleet-DB citizen** via `~/.fleet/config.toml`. It
  **consumes** `VersionRecorded` / `PublishRecorded` from the durable outbox (ADR 0019)
  instead of filesystem polling; it **writes** verdict rows + the board-resolution row
  and calls `promote()` through the fleet package.
- **A board's identity is the run_id** — board creation is idempotent, killing the
  duplicate-board failure. The outbox's startup drain kills silent watcher death (a
  down consumer misses nothing).
- **File-local stays:** board UI/layout state and the resolution sidecar. **Legacy
  folder-watcher mode remains** for non-spine renders until wave-2 migrations.
- Verdicts are designed as publishable events (the phase-2 AYON publisher subscribes —
  brief decision 11, ADR 0027).

### Hardening scope (phase 1)
The duplicate-board fix (run_id identity), the event-consumer watcher replacement,
zero-keep resolution support, and server stability (service-ification) are part of
absorbing shotgate.

## Consequences
- One review surface, one event transport. Shotgate gains a DB consumer and a promote
  call-path; the Roustabout shrinks (correct per ADR 0012's minimalism).
- New schema needed: `verdicts` + board-resolution tables (a future migration, designed
  under ADR 0027's AYON mapping constraint — verdicts map to AYON review/publish
  events).
- Shotgate reviewing stays possible with mckenna down (boards render from local state);
  only verdict recording/promote requires the DB.

## Why an ADR
It retires two accepted ADRs' worth of Roustabout duties into a system that grew up in
production, and pins the verdict contract — the one human gate every publish flows
through — before any code builds against today's sidecar-only behavior.
