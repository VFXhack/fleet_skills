# ADR 0015 — Shot code includes the Episode token: `JOB_EP_SEQ_SHOT`

**Status:** Accepted
**Date:** 2026-06-26
**Resolves:** the "Episode token in the Shot code" TBD left open by ADR 0003 / CONTEXT since Session 1.

## Context
ADR 0003 fixed the project hierarchy (Client → Job → Episode → Sequence → Shot, Episode always a level)
and observed live shot codes as `JOB_SEQUENCE_SHOT` (`AWA_SALEM_010`), explicitly leaving open whether the
**Episode** token belongs in the code. `shot_code` is the DB key — denormalized onto
`versions`/`publishes`/`deliveries` with `UNIQUE (shot_code, number)` per gate (ADR 0011) — so it must be
unique within a Job. The folder tree already encodes Episode (`<EP>/<SEQ>/<SHOT>/`), so the *path* is never
ambiguous; the open question was only about the *code*.

The deciding domain fact (Andy): **Sequence names recur across Episodes** within a Job (a `TITLE`
sequence, or a recurring location like `SALEM`, can appear in EP01 and EP02). Without the Episode token,
`AWA_SALEM_010` would collide across episodes.

## Decision
The Shot code is **`JOB_EP_SEQ_SHOT`** — e.g. **`AWA_EP01_SALEM_010`**.

- Guarantees `shot_code` uniqueness within a Job even when Sequence names repeat across Episodes.
- The code is **self-locating**: it maps directly to its `<EP>/<SEQ>/<SHOT>/` folder in the ADR-0003 tree.
- `EP01` is the canonical Episode token (one-offs still get `EP01`, per ADR 0003 "Episode always present").

## Consequences
- **Migration:** the live `AWA` project (and the fal/comfy runner scripts — per-shot `run_*.ps1`, `*.toml`,
  the Notion log) use the old `JOB_SEQ_SHOT` form; they gain the Episode token in the ADR-0003 legacy
  migration.
- `create-project` and any scaffolder stamp shot folders/codes with the Episode token.
- No DB schema change — `shot_code` stays a text column; only its format convention tightens.
- ADR 0003's stated `JOB_SEQUENCE_SHOT` examples and CONTEXT's *Project anatomy* are updated to this form.

## Why an ADR
The shot code is the DB key every artifact carries; changing its format later means re-keying rows and
re-pathing folders + scripts. A reader sees the Episode in both the tree and the code and would wonder why
it's duplicated — the recurring-sequence-name reason is the answer, on record.
