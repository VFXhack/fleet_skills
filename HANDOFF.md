# HANDOFF — for the next Claude Code agent

You are continuing a **`grill-with-docs`** (domain-modeling) effort on the `fleet-skills` repo: the
bounded context for Andy's CG → AI video pipeline. **Read `CONTEXT.md` (the glossary / source of
truth) and `adr/0001`–`0010` before doing anything.** Then read the memory `andy-working-style.md`.

## Who / how to behave
- **Andy** — solo CG→AI operator, ADHD, learning to code. **One question at a time**, concrete next
  steps, and when language is fuzzy give **2–3 concrete options + a recommendation**, then let him
  choose (`AskUserQuestion` with previews works well). Keep momentum; no sprawling tangents.
- He's a **VFX domain expert** — defer to him on VFX meaning, but **challenge contradictions** (he
  will override his own prior "LOCKED" calls; surface the trade-off first).
- **As decisions land: update `CONTEXT.md` inline and write an ADR** in `/adr` (number sequentially,
  follow 0001's format) for any non-obvious, hard-to-reverse decision. Never leave decisions only in chat.

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
- **Griptape = separate orchestration conductor** above an atomic Submitter, joined at the
  `VersionRecorded` event; Hermes (Ramdass) drives it later. (ADR 0010)
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
5. **Griptape conductor**: pick the `VersionRecorded` event mechanism (Postgres LISTEN/NOTIFY vs queue).

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
- Episode token in the Shot code? (`AWA_SALEM_010` vs `AWA_EP01_SALEM_010`)
- Term for **unvetted Block candidates** (proposed: *variant*); what a Template's **"function"** keys on.
- Document `manifest.db_project_id` as a **UUID** in `schemas/manifest.schema.json` (non-structural).
- Deferred config: Huxley `io/common` absolute prefix; Windows share name; per-machine fleet repo clone path.

## End every session with
What changed in CONTEXT.md, which ADRs were written, and the single next action.
