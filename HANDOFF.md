# HANDOFF — for the next Claude Code agent

You are continuing a **`grill-with-docs`** (domain-modeling) effort on the `fleet-skills` repo: the
bounded context for Andy's CG → AI video pipeline. **Read `CONTEXT.md` (the glossary / source of
truth) and `adr/0001`–`0016` before doing anything.** Then skim **`PIPELINE.md`** (the canon flowchart:
main Shot flow, the supervisor-only Asset Production sub-flow, and the system/provenance view — it
visualizes exactly what this handoff describes). Then read the memory `andy-working-style.md`.

## Who / how to behave
- **Andy** — solo CG→AI operator, ADHD, learning to code. **One question at a time**, concrete next
  steps, and when language is fuzzy give **2–3 concrete options + a recommendation**, then let him
  choose (`AskUserQuestion` with previews works well). Keep momentum; no sprawling tangents.
- He's a **VFX domain expert** — defer to him on VFX meaning, but **challenge contradictions** (he
  will override his own prior "LOCKED" calls; surface the trade-off first).
- **As decisions land: update `CONTEXT.md` inline and write an ADR** in `/adr` (number sequentially,
  follow 0001's format) for any non-obvious, hard-to-reverse decision. Never leave decisions only in chat.

## Session 6 (2026-06-26) — PIPELINE.md hardened to canon (do NOT re-litigate)
A `grill-with-docs` pass pressure-tested `PIPELINE.md` against the UL + ADRs, fixed 7 issues, then
modeled the per-run-type spec; all landed in PIPELINE / CONTEXT / ADRs:
- **ADR 0013** — `VersionRecorded` fires only after a take's output lands; the **Submitter** writes
  `versions.address` on render completion (Flamenco callback / sync Runner return) and emits then. "Write
  the pointer back" moved **off** the Roustabout (now no-poll, no-pointer-back). Amends 0010/0012.
- **ADR 0014** — `run.type` is ONE rich enum and the single Roustabout dispatch key
  {seed-sweep, prompt-variation, xy-plot, refine, comp, upscale, depth-pass}, orthogonal to
  `versions.stage` (render/upscale/comp = storage bucket). Refines 0005/0011.
- **ADR 0015** — Shot code includes the Episode token: `JOB_EP_SEQ_SHOT` (`AWA_EP01_SALEM_010`), because
  Sequence names recur across Episodes. Amends 0003; implies a rename in the legacy migration + runner scripts.
- **ADR 0016** — per-`run.type` **spec** contract: each type declares its variables (xy-plot axes =
  knob + explicit values, N=points; seed/prompt/comp/upscale/depth specs); all inputs via **bindings**
  (new roles `Source`, `Comp-Input`); new `runs.spec` column (migration `0002_run_spec.sql`). The
  Submitter validates `spec` against the Template's knobs, then expands it into Versions.
- **UL sharpening (CONTEXT only):** Template "function" = workflow-type/**mode** (=`runs.mode`); Block
  "function" = prompt-**purpose**. Plate/Driver & Lipsync-Dialog are Publish XOR Import; `depthXbw`
  normalized to Depth-Pass/depth-pass; **Lipsync-Dialog** added to View 1 + the Asset sub-flow + note-triage.
- DDL (`0001_initial_schema.sql`) already had `address` + the `stage` CHECK; only comments were updated.

## DONE — Session 1 grilling is COMPLETE (do NOT re-litigate; all in CONTEXT.md + ADRs, committed)
Every architectural branch is resolved. Committed in `7b0e7a6` (ADRs 0002–0010 + CONTEXT v0.3 + schemas)
and a follow-up commit (depth-pass skill).
- **Project store** on **Huxley**; `base_path` platform-neutral + per-machine resolution. (ADR 0002)
- **Project structure** shot-centric, Client→Job→Episode→Sequence→Shot, two-tier `assets/`. (ADR 0003)
- **Reconciled the prior UL handoff**; adopted Generation→**Version**. (ADR 0004)
- **Artifact / versioning / provenance**: Submit→Run→Version(`v###`)→Publish(`p###`)→Delivery(`v#`);
  Import; Lineage pointers; gated namespaces; Role-on-binding. (ADR 0005)
- **Thin Manifest** = identity + logical `base_path` + `db_project_id`; provenance DB-only. (ADR 0006)
- **Recipe storage hybrid**: authoring recipe on the Run + frozen Submission Prompt per Version (JSONB). (ADR 0007)
- **Provenance core = thin Postgres on Mckenna** (own UL); `projects` table = the project index;
  `db_project_id` = row UUID; DSN in Fleet config; Notion → one-way view; Video Generations log migrates in. (ADR 0008)
- **Spellbook = `spellbook/` folder in THIS repo** (beside `skills/`); distributed by the Git remote
  (`github.com/VFXhack/fleet_skills`) via clone + `git pull`; Notion demoted. (ADR 0009)
- **Orchestration = two floors** (ADR 0010, amended by **0012**): **Ringmaster** (agent, later; Hermes
  plays it) over **Roustabout** (deterministic worker, now — a thin Python worker), joined to the atomic
  Submitter at the `VersionRecorded` event. **Griptape demoted** from "the conductor" to a Ringmaster-floor
  candidate (vs the Claude Agent SDK); it is **not** the Roustabout.
- **depth-pass Skill** rewritten: hardened **spine** (Comfy on Huxley → depth **Publish** in
  `<Shot>/publishes/`, Run → Postgres via Submitter); concrete recipes are **variant Spells**
  (`depthcrafter-anyline-combo`, `depthcrafter-bw20`; `seedance-color2depth` deprecated).

## OPEN — next session is IMPLEMENTATION, not domain grilling
The domain model is settled; the remaining work is building it. Priority order:
1. **Postgres provenance core (START HERE).** Author the schema DDL — 7 UL-named tables (`projects`,
   `runs`, `versions`, `publishes`, `deliveries`, `assets`, `bindings`), **JSONB frozen-submission** on
   `versions`, **FK pointer edges** for lineage, per-gate counters. **Stand up Postgres on Mckenna.**
2. **`create-project` rewrite (stale).** Must: scaffold the ADR-0003 tree; insert a `projects` row and
   write the UUID into the Manifest's `db_project_id`; write the thin manifest (ADR 0006 schema).
3. **Spellbook migration.** Move Spells/Templates from Notion + the project `CLAUDE.md` recipes into
   `spellbook/`; pin the **depth-pass variant Spell** params (DepthCrafter `s5g2p0w110`, the ffmpeg
   B&W comp @20%, Anyline settings) while doing it.
4. **Notion**: one-way DB→Notion sync + a Notion→Postgres migration of the Video Generations log.
5. **Roustabout (START HERE next session).** Grill *down* into the deterministic floor: define the
   `FLOWS[run.type]` dispatch table — exactly what fires for `seed-sweep` vs `refine` vs `depth-pass`
   (proxy? contact-sheet? auto-publish? chain a stage?). Then pick the `VersionRecorded` event mechanism
   (Postgres `LISTEN/NOTIFY` vs queue). Ringmaster tool choice (Griptape vs Claude SDK) can wait.

## RECONCILIATION GAP discovered this session (important for `create-project`)
The **real on-disk projects do NOT match ADR 0003.** Live layout (e.g. `W:\Projects\WBTV\AWA\`,
`W:\Projects\HMVFX\Centenario\`) uses `AI_Renders\<SHOT>\`, `AI_Frames\`, `plates\`, `renders\`,
`comps\`, `deliverables\`, `logs\`, `docs\`, per-shot `run_*.ps1` scripts + an `awa.toml` + per-project
`CLAUDE.md`. Takes are **flat `<SHOT>_<variant>_<params>.mp4` + a sidecar `.json` recipe** (e.g.
`CTO_99_99_berniniref_seed777.json`), not `v###` in a `versions/` tree. So ADR-0003 is **aspirational**;
`create-project` either scaffolds the new tree for *new* jobs or a migration path is needed for existing
ones. Surface this to Andy before building `create-project`. (`W:` is the per-machine mount of the
project store; comfy-runner toolchain lives at `W:\Projects\ComfyUI_Tools`.)

## Micro to-confirms (cheap, fold in when relevant)
- ~~Episode token in the Shot code~~ — **resolved:** included, `JOB_EP_SEQ_SHOT` (ADR 0015).
- ~~Block-candidate term / Template "function"~~ — **resolved:** candidate = *variant*; Template fn = mode,
  Block fn = purpose (CONTEXT updated).
- Document `manifest.db_project_id` as a **UUID** in `schemas/manifest.schema.json` (non-structural).
- Deferred config: Huxley `io/common` absolute prefix; Windows share name; per-machine fleet repo clone path.

## End every session with
What changed in CONTEXT.md, which ADRs were written, and the single next action.
