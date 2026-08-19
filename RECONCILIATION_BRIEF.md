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

## R1 grill rulings (2026-08-18, after the ADR audit)

The audit (`ADR_REALITY_AUDIT.md`) surfaced six items the brief didn't rule on.
Andy's rulings:

- **R-1 · ADR 0002 amended: watts is the project store, huxley is compute.**
  Canonical project trees on watts (`D:\Projects` now, `E:` for bulk); huxley
  nvme is compute-local scratch whose keepers get pulled back and registered.
- **R-2 · Proving lane runs in a real ADR-0003 tree with real shot codes** —
  new runs only; existing `zombo_v002` artifacts stay in place and are
  referenced/backfilled. **Same treatment for WBTV POM (TPOM)** — it becomes
  the second onboarded project (pairs with the wave-1 external-API run-types).
- **R-3 · The provenance DB is the system of record; Notion becomes a view.**
  New run-types write only to the DB; comfy_runner's Notion hook survives until
  its lane migrates; any future Notion dashboard is a one-way export from the DB.
- **R-4 · The run.type enum names mechanical shapes, not recipes.** M8
  multi-stage and nobg-convert are Spells under a generic convert/gen type;
  flux2 polish dispatches as `refine`. New enum values only when
  dispatch/validation genuinely differs.
- **R-5 · One human promote seam.** Creative artifacts promote only via a
  shotgate verdict (recorded in provenance). Deterministic passes (control
  passes, plates, drivers) auto-publish boardless but still emit
  VersionRecorded, and anything can be pulled onto a board for spot-QC.
- **R-6 · Ops verified (2026-08-18):** prod `fleet` DB live on mckenna
  (PG 17.10, tailnet 100.108.34.23) but at **migration 0003** — 0004/0005 not
  applied (all tables empty, so applying is safe); `mempalace` confirmed on the
  same cluster (ADR 0025 premise holds); **no automated pg backup exists** —
  the ADR 0025 backup prerequisite is unmet. `~/.fleet/config.toml` exists on
  watts and leary.

## R2 status (2026-08-19)

- ✅ ADRs promoted: **0025** (mckenna coexistence + backup gate), **0026** (shotgate
  review context — Andy's four hardening questions grilled and answered inside it:
  verdict→promote with legal zero-keep rounds; notes on verdict + board-resolution
  rows; grades record-now-automate-later; shotgate joins the fleet DB, board id =
  run_id), **0027** (AYON mapping constraint), **0028** (watts is the project store,
  per R-1). Amended ADRs 0002/0008/0012/0018 status-stamped.
- ✅ pg_dump timer live: `pg-backup.timer` (mckenna user unit, 02:30) →
  `/mnt/shared/pg_backups`, watts task `FleetPgBackupPull` (04:00) →
  `E:\backups\mckenna_pg`. First fleet dump verified both ends. **Open:** Andy adds
  `MEMPALACE_DSN` to mckenna `~/.pg_backup_env` so the palace DB dumps too.
- ✅ watts venv created (`.venv`, `pip install -e .`, psycopg 3.3.4); watts
  `~/.fleet/config.toml` `projects_root` → `D:\Projects` per ADR 0028 (leary's
  resolver entry for the watts store is an open item).
- ⏸ Migrations 0004/0005: prod re-verified at 0003, all 8 tables empty, tool ready —
  the write itself was blocked by session permissions. Andy runs:
  `.venv\Scripts\python.exe db\apply_migrations.py --yes` (from repo root).
- ⏭ Next: Session 14's live dispatch (after migrations; Andy in the loop per ADR 0024).

## R2 agenda (queued 2026-08-19)

Openers (mechanical, in order): promote draft ADRs 0025/0026/0027 + the 0002
amendment to numbered ADRs → apply migrations 0004/0005 to prod (verified empty)
→ pg_dump timer on mckenna (ADR 0025 prerequisite) → `pip install -e .` venv on
the watts clone → Session 14's live dispatch.

**Hardening questions from Andy (2026-08-19) — these ARE the ADR 0026 contract
grill; answer them when that ADR is written, not before:**

1. **What do accept/reject actually DO?** Today: `resolve()` writes
   `shotgate_resolution.<id>.json` (absolute keep/reject/winner paths) next to
   the media and fires the board's optional `on_resolve` hook. Nothing else
   consumes it unless a hook is wired. R2 must define: verdict → provenance
   write (R-5's "one promote seam") → what downstream is *entitled* to assume.
2. **How do per-shot / per-board NOTES flow into the next round?** Today:
   stored in board state, read by humans/Claude ad hoc — no structured reuse.
   R2 must decide where notes live in the provenance model (run.note? version
   annotation?) so round N+1 prompts/recipes can cite round N's notes.
3. **How are GRADES used?** Today: verdict/score per item drive keep/reject
   counts and the resolution; scores go nowhere else. R2: do scores feed
   recipe selection (e.g. seed picks), training-pair curation, or stay human
   shorthand? Decide and record it.
4. **What is the shotgate ↔ mckenna DB relationship?** Today: none — boards
   are JSON next to media + a registry on watts. This is the ADR 0026 seam:
   which board events land in Postgres (VersionRecorded, verdicts), what stays
   file-local, and whether board identity = run_id.

## R1 scope

1. ✅ Clone to watts (this commit).
2. ✅ This brief committed.
3. ADR reality audit → `ADR_REALITY_AUDIT.md`: per-ADR verdict
   (holds / broken-by-reality / superseded-by-shotgate / untested) with evidence
   from the six weeks, plus draft superseding ADRs for decisions 3, 10, 11.
4. Andy grills the verdicts; approved ones become numbered ADRs.
5. Housekeeping alongside: CLAUDE.md split, leary D:\Tools triage inventory,
   leary → fleet_mine.
