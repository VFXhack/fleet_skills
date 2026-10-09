# ADR 0029 — Tranche attributes live in the TrancheBidding toolkit; AYON publish is a later step

**Status:** Accepted
**Date:** 2026-09-14 (session "tranchebid" grill)
**Closes:** the open thread in `D:\Projects\ChiefOfWar_bid\HANDOFF_2026-08-03.md` §"AYON tranche definition"
**Relates to:** ADR 0026 (shotgate is the review context), ADR 0027 (provenance schema maps onto AYON)

## Context
The August 2026 GCI bid sessions began defining a *tranche* as an AYON-legible entity
(key = location × methodology; eight attributes) and paused on naming and units. Since then
the bidding work has been consolidated into a toolkit, `D:\Tools\TrancheBidding`, whose
design (`docs/DESIGN.md`) settles those questions for the bidding context: a tranche is
derived from shot tags by ordered rules, its attributes are **Mode, Rule, Dev Shot, Ladder,
Carry, RFT Rate, Variant Discount**, units are hours per task, and the hero is a shot flag.

## Decision
- The **bidding bounded context owns the tranche definition.** Its schema is
  `TrancheBidding/docs/SPEC_shotlist_schema.md`; fleet pipeline code does not redefine it.
- **AYON publish is out of scope for v1** of the toolkit. The accepted shot list already has
  permanent ids (`<SHOW>_0010` stepping by ten, omit keeps the id) and carries the tranche
  as a self-contained object, so a later `publish-ayon` (folders from the cut list, plates as
  v001, tranche attributes on a tranche folder entity, dollars staying in the workbook)
  needs no schema change. It goes through the `ayon-outbox` skill when a bid becomes a job.
- The bid workbook is a **target**, not a vocabulary owner: the studio taxonomy in the
  toolkit rewrites the workbook's dropdowns, never the reverse.

## Consequences
- The August naming alternatives (Base / Step / Note Cost, Floor / Ramp / Patch) are retired.
- Provenance (ADR 0027) can reference a shot's tranche by key without a join to the bid
  workbook; the tranche's `dev` hours are the natural "budget" attribute for shotgate boards
  when a job starts.
- Bidding stays out of `fleet_skills`; this ADR is the only pointer.
