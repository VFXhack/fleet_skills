# Reconciliation Brief — Session R1 kickoff

**Date:** 2026-08-18 · **Decided by:** Andy (grilled decision-by-decision) · **Status:** approved, R1 in progress

The system stalled at Session 13 (2026-07-06). Six weeks of production happened outside it:
shotgate (now the fleet-wide review server), comfy_runner, the zombo v002 lanes
(M8 latent multi-stage, flux2 polish, LTX union control, bernini v2v, magnific),
and a live provenance forensics case (3z_ltx_union_roll2_bw, 2026-08-18) that proved
both the need for the provenance core and the failure modes of not having it:
unrecorded ffmpeg steps, renames severing lineage, runs bypassing submitters with sidecars.

This brief records the decisions that govern the reconciliation. The ADR audit
(`ADR_REALITY_AUDIT.md`) executes against it.

## Decisions

1. **Reconciliation before new code.** Audit all 24 ADRs against production reality;
   write superseding/amending ADRs; only then resume building (Session 14's live-test
   dispatch waits).
2. **Watts is primary; git is the mirror.** Canonical dev home is
   `watts:D:\Tools\dev\fleet_skills`. Leary keeps its clone. No file-level mirroring
   of code between machines, ever.
3. **Shotgate is absorbed as the review bounded context.** It owns boards / watchers /
   verdicts. The roustabout event ADRs (0012, 0018, 0019) are reconciled into
   shotgate's contract rather than built as a second event system.
   Hardening punch-list (from production): duplicate/competing boards per folder,
   watchers dying silently (idle timeout, no notification), server/UI instability.
   Verdict persistence is NOT broken.
4. **Proving lane: zombo stills v2 ("nobg singletons").** Solo EEVEE render →
   Qwen/M8 convert → difference matte → paste-back → flux2 polish dn35, run on real
   5Z/7Z/9Z production. First shot through the full spine (submit → run → provenance
   → board → verdict → provenance) defines phase-1 done.
5. **Wave-1 run-types:** the stills-v2 chain steps + the Blender control-pass builder
   (ADR 0017's case, with the depthwire gray-plane/yuv420p-last chroma fix baked in)
   + the Magnific/external-API lanes. LTX union and bernini stay documented manual
   recipes until wave 2.
6. **Provenance: forward-only + active-project backfill.** Every spine run records
   provenance from day one. Backfill only live zombo shots (3Z/5Z/7Z/9Z).
7. **Sessions: global fleet context + per-project starts.** Fleet-wide facts move to
   `~/.claude/CLAUDE.md` on each workstation; sessions start in the project/tool dir
   being worked on, with thin local CLAUDE.mds and scoped memory.
8. **Leary↔watts gap: triage, not mirror.** Shared code → git repos with one head.
   One-off dirs (butterfly_diagrams, promise_ayon, src, bin) → inventoried into
   project homes or archive. Leary gets added to mckenna's fleet_mine harvest so its
   content reaches the palace without living on watts.
9. **Phase-1 definition of done:** reconciliation ADRs merged · fleet_skills running
   from watts · shotgate's three failure modes fixed · one real shot through the
   stills-v2 lane end-to-end with provenance recorded · a provenance report generated
   from the DB instead of forensics.

## Amendments (post-ADR infrastructure that now exists)

10. **Provenance core proposed home: mckenna Postgres.** A new `provenance` database
    beside the palace's pgvector DB. Artifacts stay file-based per ADR 0002 — the DB
    stores records that point at files, never pixels. MemPalace stays the narrative
    layer (verdicts/decisions/gotchas via fleet_mine); run records do NOT become
    drawers. R1 reads ADR 0008/0011 first; this walks in as the strong default.
    Prerequisite it creates: a real backup story for mckenna.
11. **AYON is a design constraint now, an integration later.** The provenance schema
    must map 1:1 onto AYON's product/version/representation model, and shotgate
    verdicts are designed as publishable events. Phase 2 wires an AYON publisher
    (keeps → huxley sandbox auto-publish = the Bid-to-AYON bootstrap demo for
    Promise). No AYON code in phase 1.
12. **Ramdass/Hermes split.** Fleet onboarding (headless boot, tailnet, SSH, KG
    facts) happens opportunistically whenever the machine is awake — independent of
    phase 1. Hermes agents wait for phase 2 and become the first external consumer of
    the submitter/event contract. The reconciliation keeps the conductor/ringmaster
    seat (ADR 0010) explicitly open for a Hermes-on-ramdass host.

## Phase-2 queue (rough order)

- AYON publisher (shotgate keeps → sandbox publish; Promise demo).
- Hermes agents on ramdass against the hardened contract.
- LTX union + bernini run-types; remaining launcher migrations
  (mocap_runner, sam3, smpl, blender render).

## R1 scope

1. ✅ Clone to watts (this commit).
2. ✅ This brief committed.
3. ADR reality audit → `ADR_REALITY_AUDIT.md`: per-ADR verdict
   (holds / broken-by-reality / superseded-by-shotgate / untested) with evidence
   from the six weeks, plus draft superseding ADRs for decisions 3, 10, 11.
4. Andy grills the verdicts; approved ones become numbered ADRs.
5. Housekeeping alongside: CLAUDE.md split, leary D:\Tools triage inventory,
   leary → fleet_mine.
