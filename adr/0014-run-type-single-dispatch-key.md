# ADR 0014 — `run.type` is one rich dispatch-key enum, orthogonal to `versions.stage`

**Status:** Accepted
**Date:** 2026-06-26
**Refines:** ADR 0005, ADR 0011 (the open-ended `runs.type` enum); feeds ADR 0012 (Roustabout dispatch)

## Context
ADRs 0005/0011 fixed `runs.type ∈ {seed-sweep, prompt-variation, xy-plot, refine, …}` and a separate
`versions.stage ∈ {render, upscale, comp}`, leaving the type enum open ("…"). Hardening `PIPELINE.md`
exposed an overload: `comp` was being used as **both** a run.type and a stage, and up-res had a stage
(`upscale`) but no run.type — yet the Roustabout is specified to dispatch on `FLOWS[run.type]` (ADR 0012).
The two words conflate two ideas: the **sweep/authoring shape** of a gen run vs. the **operation/bucket**
a take belongs to.

Three models were weighed: (A) one rich `run.type` enum that absorbs the operations, with `stage` as a
pure storage bucket; (B) two orthogonal axes — `run.type` = sweep-shape only, operation lives in `stage` —
dispatched on a composite key; (C) make `run.type` the operation and move sweep-shape to a secondary
`mode` field.

## Decision
**Model A.** `run.type` is a **single rich enum and the single Roustabout dispatch key**:
`{seed-sweep, prompt-variation, xy-plot, refine, comp, upscale, depth-pass}`. `versions.stage`
`{render, upscale, comp}` records **only** which `versions/<stage>/` bucket a take lands in
(`comp`→comp, `upscale`→upscale, every gen sweep-shape→render).

- The Roustabout dispatches on one `FLOWS[run.type]` table; it may **sub-branch on `stage`/Role** inside a
  flow (consistent with ADR 0012's "branches by run.type / Role / stage").
- `upscale` is the canonical token; "up-res" is the friendly verb. `depth-pass` was already a run.type in
  CONTEXT (a depth-pass Run produces a depth Publish), so this only adds `comp` and `upscale` explicitly.

Rejected: (B) — conceptually cleaner, but a composite-key dispatch is more code for a solo operator
levelling up, and it fights the existing `FLOWS[run.type]` phrasing; (C) — most VFX-honest (stages =
departments) but the largest rename (run.type enum + Submitter authoring recipe + every doc), unjustified
now.

## Consequences
- `run.type` and `stage` **overlap** for `comp`/`upscale` (the run.type implies the stage). Accepted as the
  price of single-key dispatch; the `stage` column stays because the four gen sweep-shapes all map to the
  one `render` stage, so stage is not derivable from type in the common case.
- The `FLOWS[run.type]` table (next implementation, HANDOFF §OPEN 5) keys on these seven values.
- No schema change: `runs.type` was already a text column with an open enum; this fixes the value set.

## Why an ADR
It resolves an overload that a reader of 0005/0011 hits directly (comp as both type and stage), picks one
of three real models, and pins the dispatch contract the Roustabout is built against. Reversing it means
re-tagging runs and re-cutting the dispatch table.
