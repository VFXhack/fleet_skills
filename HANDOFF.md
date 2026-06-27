# HANDOFF — for the next Claude Code agent

You are continuing a **`grill-with-docs`** (domain-modeling) effort on the `fleet-skills` repo: the
bounded context for Andy's CG → AI video pipeline. **Read `CONTEXT.md` (the glossary / source of
truth) and `adr/0001`–`0017` before doing anything.** Then skim **`PIPELINE.md`** (the canon flowchart:
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

## Session 7 (2026-06-26) — `control-pass` generalizes `depth-pass` (do NOT re-litigate)
Andy's call: depth isn't special — it's one flavor of a whole family of control/structure inputs.
- **ADR 0017** — replaced the `depth-pass` `run.type` with **`control-pass`**: depth, canny, openpose,
  matte are **one run.type** (one Roustabout flow), the **flavor is a Spell** named by `spec.method`
  (`depthcrafter-bw20`, `canny`, `openpose`, `matte-*`, …), output bound in a **per-kind Role**
  (Depth-Pass / Canny / OpenPose / Matte). Scope = control/structure maps only; **audio + creative assets
  out**. Amends 0014 (enum) + 0016 (spec row). No schema change (open text type; `runs.spec` exists).
- **Where "what a run does" lives (Andy's question, settled):** `run.type` = dispatch shape (code/DB enum);
  `spec` = this run's variables incl. `method` (DB, on the Run); **the Spell in the Spellbook = the actual
  craft** (the ComfyUI graph / ffmpeg comp). `spec.method` is the seam pointing a Run at its Spell. For gen
  runs a **Template** (Spellbook) also holds the prompt pattern + knob declarations the Submitter validates.
- **Touched (control-pass):** ADR 0017 (new); 0014/0016/0011 enum notes; CONTEXT (`Run`, `Seed Sweep`, new
  `Control Pass` entry replacing `Depth Pass`, Role values, open-Qs); PIPELINE (DEPTH node→Control-Pass,
  bind edge, View 1b text+table, writes table); `skills/depth-pass/SKILL.md`→v0.3 (now the depth family of
  control-pass; Run logs `type: control-pass` + `spec.method`).

### Then: grilled the Roustabout `FLOWS` to completion (§OPEN 5 — done)
- **ADR 0018 — Roustabout FLOWS.** Two tiers on `VersionRecorded`: **per-take** (proxy/thumbnail + log) and
  a **per-run completion barrier** ("N of N landed", a deterministic count it *reads* from the spec
  expansion, ADR 0016) → contact-sheet if >1 take, one "run done" notify, **auto-publish**. **Auto-publish
  bounded:** only `type ∈ {control-pass, upscale, comp}` ∧ `version_count == 1` (creative sweeps never —
  picking a take is judgment); single-output comp/up-res internal gate goes auto, human check moves to
  QC/client-gate. **Wired chains:** the Roustabout may auto-submit new Runs ONLY for judgment-free
  `(trigger + Role/tag) → fully-pinned Run recipe` transitions (default Spell, fixed params); a short
  explicit `CHAINS` registry, not a workflow graph. **New event `PublishRecorded`** (Submitter emits on
  every publish insert — auto or human promote) drives chains.
- **ADR 0019 — Event delivery.** `LISTEN/NOTIFY` as a wakeup over a **durable `events` outbox** (row
  written same-txn as the version/publish insert); Roustabout drains pending on startup → nothing lost;
  **at-least-once → idempotent handlers**. Rejected pure NOTIFY (lossy) and an external broker (premature).
- **Touched (FLOWS):** ADR 0018 + 0019 (new); CONTEXT (Roustabout entry rewritten, Submitter entry, new
  `Orchestration events` entry, status→v0.8, open-Qs); PIPELINE (ROUST node, event seam + `events` outbox
  node, promote/gate, writes table +`PublishRecorded` row, open-items→resolved).

### Then: built the Roustabout spine (the chosen implementation start)
- **`db/migrations/0003_events_outbox.sql`** — the durable `events` outbox table (ADR 0019):
  `type ∈ {VersionRecorded,PublishRecorded}`, `subject_id`, `payload jsonb`, `status`, `attempts`,
  `UNIQUE(type,subject_id)` for emission idempotency, partial `events_pending_idx`. No trigger — the
  Submitter does INSERT + NOTIFY in its app txn.
- **`roustabout/`** — the thin Python worker (psycopg 3.3, Python 3.13): `config.py` (DSN per db/README +
  `EVENT_CHANNEL='fleet_events'`), `worker.py` (LISTEN/NOTIFY + 30s poll backstop; claim with
  `FOR UPDATE SKIP LOCKED`; savepoint per handler; retry→`error` after 5; startup backlog drain),
  `handlers.py` (dispatch; **REAL**: run-completion barrier + auto-publish eligibility + take log;
  **STUB**: proxy/contact-sheet/notify, and auto-publish-write/chains which must go via the Submitter),
  README + requirements.
- **Verified (no live DB):** `py_compile` + import clean; eligibility truth-table + dispatch routing pass.
  NOT run against Postgres (Mckenna DB may not be stood up; don't mutate the real store without Andy).

### Then: built the Submitter emit path (chosen next slice)
- **`submitter/`** — `events.py`: `emit_version_recorded(conn, version_id)` + `emit_publish_recorded(conn,
  publish_id, role=…)` — INSERT into `events` (ON CONFLICT DO NOTHING) + `pg_notify('fleet_events', …)`,
  **inside the caller's txn** (transactional outbox); both enrich payload via a join (run_id/shot_code/
  run_type, +role/tag for publishes). `config.py` (DSN + channel, duplicated from roustabout — unify into a
  shared `fleet` module when a 3rd consumer lands; noted as cleanup). `emit_demo.py` — opt-in CLI
  (`python -m submitter.emit_demo version|publish <id>`) to smoke-test the spine end-to-end. README.
- **Verified (no live DB):** py_compile + imports clean; `Json` adapter resolves; `emit_demo --help` OK;
  channel name `fleet_events` consistent across migration + both config.py.
- **Not built:** the write path that CALLS emit (`record_landed_take`, `promote` w/ p### allocation), the
  rest of the Submitter (ingest/expand/dispatch), and a persisted publish tag/role for chain matching.

### Then: built the Submitter write path (`submitter/writes.py`)
- `record_landed_take(conn, version_id, address)` — UPDATE `versions.address` + `emit_version_recorded`,
  one txn (ADR 0013); idempotent.
- `promote(conn, version_id, path=…, role=…)` — per-shot advisory lock → allocate next `p###`
  (`COALESCE(MAX(number),0)+1`, writer-allocated per ADR 0008) → INSERT publish → `emit_publish_recorded`;
  returns `(publish_id, number)`. This is the call-site for BOTH a human gate and the Roustabout's
  auto-publish. Verified py_compile/import (no live DB).

**Single next action (START HERE):** the code spine is complete (Submitter emit+write path → outbox →
Roustabout drain → handlers). The only thing left for a **real end-to-end proof is live infra**, which
needs Andy's hands: **stand up Postgres on Mckenna, apply migrations `0001`–`0003`**, then in two terminals
run `python -m roustabout.worker` and `python -m submitter.emit_demo version <id>` against a seeded
run/version row — watch the barrier/eligibility/stub-handler logs fire. After that proves out: wire the
first `CHAINS` entry (Hero → depth `control-pass`) and/or build the Submitter ingest/dispatch slice. The
deferred **Branch 6** (real control-pass method Spells) remains available as an independent track.

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

**Single next action (START HERE):** grill the **Roustabout `FLOWS[run.type]`** (see §OPEN 5) — for each of
the 7 types, what fires on `VersionRecorded`: proxy/thumbnail (always?), contact-sheet (for grid types
xy-plot/seed-sweep?), auto-publish (depth-pass → its depth Publish; upscale?), chain next stage? Then pick
the event mechanism (Postgres `LISTEN/NOTIFY` vs a queue). **Now unblocked** by ADR 0016 — the Roustabout
wakes with a typed, validated `spec` and a known version count. Two tiny non-blocking cleanups noted this
session: align `skills/depth-pass/SKILL.md`'s `depthXbw20` filename token with the `depthcrafter-bw20`
variant Spell; and `job_code` is only unique per-client (so `shot_code` is per-Job unique, not global).

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
5. **Roustabout `FLOWS` — DESIGN DONE (ADR 0018/0019, Session 7); now IMPLEMENT.** The dispatch model is
   settled (two-tier reactions, bounded auto-publish, wired chains, `PublishRecorded`, `LISTEN/NOTIFY` +
   durable `events` outbox). Build it: the **`events` outbox** (`0003_events_outbox.sql`) + the thin Python
   worker (LISTEN + drain + idempotent handlers), the `FLOWS[run.type]` + `CHAINS` tables in code, and the
   first chain (Hero → depth `control-pass`). Ringmaster tool choice (Griptape vs Claude SDK) can still wait.

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
