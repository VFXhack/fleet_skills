# ADR 0024 — The Submitter submits a Run and nothing else; validation is a separate stamping gate

**Status:** Accepted
**Date:** 2026-07-06 (Session 13)
**Builds on:** ADR 0007 (authoring vs resolved recipe), 0010/0012 (Submitter is one atomic tool;
orchestration is the Roustabout's), 0013 (`VersionRecorded` fires after a take lands), 0016 (per-type
spec → the Submitter expands into Versions), 0020/0021/0023 (Cast authors the Run)

## Context
ADR 0016 said "the Submitter expands `spec` into Versions", and CONTEXT described the Submitter as
"ingests a brief/recipe → writes the Run/Version → dispatches → writes address → emits". But since then
**Cast** (ADR 0020/0021) was built, and Cast already writes the `runs` row + `bindings` (the authoring
recipe). So the original "the Submitter writes the Run" overlaps a tool that now exists. Before building
the Submitter's front half we had to settle: **does the Submitter also *author* Runs, or does it pick up
an already-authored Run?** And ADR 0016's "validate `spec` against the Template's declared knobs" has no
Template/Spellbook store to validate against yet — so where does validation live?

## Decision
**The Submitter has exactly one job: submit one already-authored Run, by id.** It does NOT author (that
is a *family* of front-ends — Cast today, a direct-author tool later, fixtures in test — that all feed
it) and it does NOT orchestrate downstream work (that is the Roustabout, fired by events). Concretely
`submit <run_id>`:
1. loads the Run (`type` + `spec` + `params` + `shot_code`),
2. **checks a validation stamp** (see below),
3. **expands** `spec` → N `versions` (ADR 0016), each with `delta` + a `frozen_submission` snapshot,
4. **dispatches** each Version to a Runner.

**Validation is its own separate gate, not part of the Submitter (Andy's call).** A future `validate`
tool stamps a Run "checked — meets its output requirements" *at authoring time*; any tool that needs a
sound Run (cast / promote / submit) *calls the validator* rather than re-implementing the check, and the
validator memoizes via the stamp so an unchanged Run is validated once, not once per consumer. The
Submitter only **checks the stamp**; if absent it may ask the validator to run. **Because Runs are
immutable** — nothing does `UPDATE runs`, and an Override never edits a Run (it re-casts to a *new*
run_id, ADR 0013 forward-only) — **the stamp can never go stale**: validate once at birth, trust forever.
The one narrow exception is Cast's convergent binding *adding* a `bindings` row post-birth; that is the
only event that could warrant a re-stamp.

**Build order: expand first, dispatch second.** Expand is pure DB writes to `fleet_test` (isolable,
side-effect-free, unit-testable). Dispatch spends credits / hits an external API, so it is built and run
with Andy in the loop, never in self-prove.

## Consequences
- **No new authoring surface in the Submitter.** `insert_cast_run` (repository) stays the shared Run
  writer; Cast and any future direct-author front-end both use it, then hand the `run_id` to `submit`.
- **`expand` is spec-agnostic** and lives as a pure function (`submitter/expand.py`): the whole ADR-0016
  sweep grammar (explicit values, points-not-intervals, range sugar, param-key knobs) is testable without
  a DB. `write_versions` (`submitter/writes.py`) allocates the per-Shot `v###` counter like `promote`
  allocates `p###`, and refuses to double-expand a Run (once per generation).
- **The validation stamp is a marked SEAM for now** (`check_validated`), not yet a schema column — it
  needs the Template store to validate knob names against (ADR 0016). Building that store, the validator
  tool, and the stamp column is a separate future slice. `submit` reports the seam so it never implies a
  check that did not happen.
- **Two authoring-layer gaps surfaced and are logged in HANDOFF** (NOT the Submitter's to fix): `spec`
  is threaded nowhere through Hoist/Cast (a cast Run has `spec='{}'`), and there is no per-Shot *forward
  re-cast* to mint a new Run when an Override changes after a Shot is already cast.

## Why an ADR
It reverses the literal reading of ADR 0016 / CONTEXT ("the Submitter writes the Run") now that Cast
authors, pins the single-responsibility boundary every future authoring tool depends on, and records that
validation is a standalone memoized gate rather than Submitter-internal logic — a hard-to-reverse shape
choice that the validator, Cast, promote, and the Roustabout will all build against.
