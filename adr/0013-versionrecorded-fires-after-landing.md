# ADR 0013 — `VersionRecorded` fires after the take lands; the Submitter writes the output address

**Status:** Accepted
**Date:** 2026-06-26
**Amends:** ADR 0010, ADR 0012 (the `VersionRecorded` seam — division of labor at the event)

## Context
ADRs 0010/0012 fixed the orchestration seam as the **`VersionRecorded`** event: the atomic Submitter
emits it after writing the Run/Version and dispatching the render; the **Roustabout** reacts (proxy,
pointer-back, chain). Both ADRs listed "**write the pointer back**" as the Roustabout's job and described
the Submitter as "dispatch heavy render → emit `VersionRecorded`" — i.e. emit at *dispatch* time.

Hardening `PIPELINE.md` surfaced a contradiction: a Version's **output `address`** (the rendered file)
does not exist at dispatch time. Heavy renders run **asynchronously** on Flamenco (and on some Runners);
the output only lands later. If `VersionRecorded` fired at dispatch, the Roustabout would wake to a
Version row whose `address` is still empty — so it could not "write the pointer back" without first
detecting render completion itself (polling Flamenco), which pushes waiting/looping logic onto the
deterministic floor that ADR 0012 deliberately kept minimal.

## Decision
**`VersionRecorded` fires only after the take's output has landed and its `address` is persisted** — the
event means *a finished, addressable take exists*, not *a render was requested*.

- The **Submitter** owns the completion path. It `INSERT`s the Version row (with `frozen_submission`,
  `address` **NULL**) and dispatches; then, **on render completion** — a Flamenco-controller callback for
  async renders, or the synchronous return of a fal/Comfy Runner — it `UPDATE`s `versions.address` and
  **emits `VersionRecorded`**. Writing the output address is a **ledger write**, so it stays with the
  single ledger-writer; it is *not* orchestration.
- The **Roustabout** never writes the address and never polls. It reacts to a guaranteed-existing
  artifact and does only the deterministic post-work: render the proxy/thumbnail, log, notify, chain the
  next stage.
- This pins a nullable **`address`** column on `versions` (written at completion) — folded into ADR 0011's
  schema.

## Consequences
- **Amends 0010/0012:** "write the pointer back" moves **off** the Roustabout and onto the Submitter's
  completion path; "dispatch → emit" becomes "dispatch → (on completion) write address → emit." The
  atomic-Submitter model and the single-event seam are preserved — the Submitter simply gains a second,
  event-driven entry point (the completion callback) that is still a pure ledger write + emit, with no
  next-step decisions.
- The Roustabout stays strictly **no-wait, no-judgment**: every flow it runs can assume the artifact is
  real and addressable.
- An async-render **completion signal** is now explicit in the model (Flamenco callback / Runner return).
  Its exact mechanism (webhook, a status poll by the Submitter, a queue) is deferred implementation
  detail; the contract — *address persisted before emit* — is what is fixed here.
- `versions.address` is **nullable** between Submit and completion; nothing downstream may read a Version
  whose address is still NULL — consistent with "downstream references only Publishes/Deliveries" (0005).

## Why an ADR
It amends two Accepted ADRs by moving a named responsibility (pointer-back) across the
Submitter↔Roustabout seam and redefining when the seam's only event fires. A reader of 0010/0012 would
otherwise assume the Roustabout writes the address and that `VersionRecorded` fires at dispatch — both now
false. The event contract is depended on by every reactor, so the change is on record.
