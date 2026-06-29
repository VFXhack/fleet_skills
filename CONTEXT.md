# CONTEXT.md — Fleet Production System

> This is the **ubiquitous language** for the Fleet production pipeline: the shared
> glossary used by the code, by Andy, and by any AI agent working in this repo.
> It is the source of truth for what words *mean*. Keep it tight. Sharpen terms here
> via `grill-with-docs` sessions; record non-obvious decisions as ADRs in `/adr`.
>
> **Status:** v0.8 (2026-06-26) — Session 7. (1) Generalized `depth-pass` → **`control-pass`**: depth,
> canny, openpose, mattes are **one run.type**, flavored by a **Spell** via `spec.method`, each bound in a
> per-kind **Role** (ADR 0017, amending 0014/0016). (2) Pinned the **Roustabout `FLOWS`**: two-tier
> reactions (per-take + a per-run completion barrier), **bounded auto-publish** (control-pass + single-output
> upscale/comp), **wired judgment-free chains**, and a second event **`PublishRecorded`** (ADR 0018);
> delivery is **`LISTEN/NOTIFY` over a durable `events` outbox** (ADR 0019). Prior (Session 6)
> PIPELINE-hardening canon stands:
> `VersionRecorded` fires after the take lands & the Submitter writes the address (ADR 0013); `run.type`
> is one rich Roustabout dispatch enum, orthogonal to `stage` (ADR 0014); the Shot code gains the Episode
> token `JOB_EP_SEQ_SHOT` (ADR 0015); Template "function" = mode, Block "function" = purpose; the
> per-`run.type` **spec** contract + `runs.spec` (ADR 0016). ADRs 0002–0017.

---

## Glossary

### Skill
A **Claude Code skill**: a single, atomic, callable capability with a `SKILL.md`
(name, when-to-use trigger, inputs, steps, outputs). Reusable and invoked by name.
Lives in this repo under `skills/`. Skills are the *hardened* units of the system.

### Spell
An entry in the **Spellbook**: a documented recipe — a collection of actions (manual
+ automated) to achieve an outcome. A spell may **invoke one or more Skills** and may
include human steps. Spells are the *working* layer where methods first get written down.
- A **Spell graduates into a Skill** when it's invoked often enough to be worth hardening.
- A **Spell may contain Skills**, but a **Skill never depends on a Spell** (skills stay atomic).
A Spell is a **procedure**; it is *not* a **Template** (a prompt pattern) — both live in the Spellbook.

### Spellbook
The shared, **project-agnostic** library of reusable craft. **Formerly the "cookbook."** Holds **two**
entry types: **Spells** (recipes/procedures) and **Templates** (verified prompt patterns — the
core-domain prompt-authoring craft). Lives as a **`spellbook/` folder in this repo** beside `skills/`
(`spells/`, `templates/`, `templates/blocks/`) and is distributed across the Fleet by the repo's Git
remote — clone + `git pull` per workstation (ADR 0009). Notion is no longer its source of truth.

### Brief
The **shorthand creative request a human types** — it carries *intent*. The input to prompt authoring;
not a stored artifact class on its own (today it blends intent + render params; may split later).

### Submission Prompt
The **final, model-specific string** actually sent to the model — the core-domain **output** of prompt
authoring. A Brief becomes a Submission Prompt, usually via a **Template**.

### Template
A **verified, reusable prompt pattern** that turns a Brief into a **Submission Prompt** for a specific
**model + workflow-type** — a Template's "function" = the generation **mode** (`t2v`/`i2v`/`r2v`, matching
`runs.mode`). The core craft of the pipeline; lives in the **Spellbook**, project-agnostic. Built from
**Blocks** (each keyed by **prompt-purpose** — see *Block*). Spellbook index: Templates by **model × mode**.
*Verification is the goal* — today's prompt patterns are largely **unvetted**; the Template Library is a
capability **to build**, not a current asset.

### Block
A **model- and purpose-specific unit of a Template** — a reusable prompt fragment keyed by
**prompt-purpose** (camera / style / lighting / motion / subject …), whose wording is settled by
**experimentation + verification**, then composed into Templates. (A Block's "function" is its
**purpose**; a Template's "function" is its **workflow-type/mode** — the two levels key on different
axes.) Spellbook index: Blocks by **model × purpose**. Tested candidates of a Block are **variants**.
_Avoid_: **Version** for a Block's candidates — "Version" is reserved for a Run's takes.

### Project anatomy (Client → Job → Episode → Sequence → Shot)
Production work nests in five fixed levels. A **Project = a Job** — the Job is the unit that
gets a folder root, a `manifest.json`, and a `CONTEXT.md`, and is created via `create-project`.

- **Client** — the entity the work is for. Identified by a short **`client_code`** (e.g. `WBTV`).
- **Job** *(= Project)* — one commissioned body of work for a Client. Identified by a
  **`job_code`** (e.g. `AWA`). The Job folder is the Project root / `base_path`.
- **Episode** — an installment within a Job. **Always present** as a level, even for
  single-episode Jobs (one-offs get one Episode).
- **Sequence** — a named group of Shots within an Episode (e.g. `SALEM`, `JUGDEAD`, `TITLE`) that
  **carries a Sequence Pattern its Shots inherit live** (shared LUT/CFG/workflow params, shared
  Asset→Role bindings, and re-runnable recipes like the depth-pass). A Shot may **override** an inherited
  value locally; an approved change on the **look-dev Shot** is **Hoisted** up to the Sequence so siblings
  inherit it. Backed by a small `sequences` config record + Pattern in the DB (ADR 0020) — but a
  Sequence's *existence* is still its folder in the tree, not the row. See *Sequence inheritance*.
- **Shot** — the atomic unit of production: one continuous gen-AI video segment, the thing a
  **Run** acts on. Coded `JOB_EP_SEQ_SHOT` (e.g. `AWA_EP01_SALEM_010`) — the Episode token is
  **included** because Sequence names recur across Episodes, and the code self-locates to its
  `<EP>/<SEQ>/<SHOT>/` folder (ADR 0015).

_Avoid_: using "project" for a shot or a deliverable — a Project is the **Job**.
_Avoid_: **Show** (use *Episode*), **Scene** (use *Sequence* — "scene" carries narrative ambiguity).
The concept word is **Project**; **`job_code`** is its identifier. **Client** is the top organizing
folder but is **not** part of a Shot's identity (it's an attribute/parent, not a spine coordinate).

### Sequence inheritance — Sequence Pattern, Hoist, Override (ADR 0020)
A **Sequence** carries a **Sequence Pattern** — the master recipe pattern every Shot is built to,
developed on one **look-dev Shot** and **Hoisted** up — which Shots **instantiate** at Run-submit time.

- **Sharing class** — every Shot input is one of three (the rule that decides what propagates):
  - **shared-content** — one artifact, every Shot uses it (character sheet). Stored as a
    `scope='sequence'` Asset.
  - **shared-recipe** — same settings, each Shot **regenerates its own content** (e.g. a depth-pass —
    nothing special, just a `control-pass` Run type auto-published no-look by the Roustabout). Stored as a
    prototype Run in the Pattern; the consuming Role records which Run produces it
    (`produced_by_pattern_run_id`). The class is assigned **at Hoist**.
  - **per-shot** — different input each Shot, no sharing (audio). Stored as a `scope='shot'` Asset.
  Shared **params** (LUT weights, CFG, model/tier/mode) act like shared-content (one inherited value).
- **Sequence Pattern** — a **set of prototype Runs** (render, depth/control-pass, …) mirroring a Run's
  recipe **minus per-Shot content**, each Role/param tagged with its sharing class. A Shot
  **instantiates** it: shared-content auto-binds, shared-recipe **re-runs** for that Shot, per-shot slots
  are flagged "you owe an input." (Named **Pattern**, not "Template/Recipe/Spec" — those are taken; not
  "Blueprint" — avoids the Unreal collision.)
- **Look-dev (Target) Shot** — the one Shot designated to develop and iterate the Sequence's look; an
  ordinary Shot that also serves as the source the Pattern is Hoisted **from**. At most one per Sequence.
- **Hoist** — the upward verb: lift an **approved** look-dev Shot's recipe **up** into the Pattern,
  **selectively, by sharing class** — shared-content Assets and shared-recipe settings and shared params
  go up; per-shot inputs do **not**. The look-dev Shot's now-redundant overrides for the hoisted
  attributes are **cleared**; other non-overriding Shots inherit the change on their **next** Run. Hoist
  never rewrites existing takes — provenance is immutable; siblings **re-run forward** (ADR 0013).
- **Override** — a Shot setting its own value for an inherited attribute. The Shot uses its own value
  **and** stops following later Sequence-wide changes to it (override = local value **and** shield); a
  Hoist does not disturb a sibling that holds its own override.

_Avoid_: calling Hoist a **promote** — *promote* is the **gate** verb (Version→Publish→Delivery).
**Hoist** moves a value **up the structure** (Shot→Sequence); it does not move a take across a gate.

### Submitter
The connective tissue of the pipeline and an **atomic tool** (ADR 0010): **ingests** a brief/recipe →
**writes** the Run/Version to the **Postgres provenance store** on **Mckenna** (`versions.address` NULL
at this point) → **dispatches** heavy render work to **Flamenco** (or a **Runner**) → **on render
completion** writes the take's output **`address`** back and **emits `VersionRecorded`** — so the event
always means *a finished, addressable take exists*, never *a render was requested* (ADR 0013). It is also
the **sole event emitter**: on every **publish** insert (the Roustabout's auto-publish **or** a human
supervisor-gate promote) it emits **`PublishRecorded`** (ADR 0018). Both events are written as durable
**`events` outbox** rows in the **same transaction** as the version/publish insert, then `NOTIFY`-ed
(ADR 0019). It does **not** orchestrate downstream work (proxy, next steps) — that is the **Roustabout**'s
job, fired by the event.
_Avoid_: putting next-step / orchestration logic in the Submitter (or in DB triggers); emitting
`VersionRecorded` before the output has landed.

### Orchestration (the Circus: Ringmaster over Roustabout)
The post-`VersionRecorded` side of the system, split into **two named floors** (ADR 0012, amending 0010).
The metaphor is **the Circus**: a **Ringmaster** directs the show; **Roustabouts** rig between acts. The
seam to the **Submitter** is always the **event**, never an in-process call or a DB trigger.

### Roustabout
The **deterministic floor of orchestration — the crew that rigs between acts (now).** Subscribes to
orchestration **events** and runs **pre-wired flows** (full model in ADR 0018). **Rule-based, no LLM, no
judgment** — if a step needs to *judge*, that logic belongs **up** in the **Ringmaster**. It **calls** the
Submitter as one instrument; it is not the Submitter. (Every take's **`address`** is already written by the
Submitter at render completion — ADR 0013 — so the Roustabout reacts to a guaranteed-existing artifact and
never writes the pointer or polls.) Its authority (ADR 0018):
- **Two tiers on `VersionRecorded`.** **Per-take:** render the **proxy/thumbnail** + write a **structured
  log**. **Per-run (a completion barrier — "N of N versions landed", a deterministic count it *reads*, ADR
  0016):** assemble a **contact sheet** when the run made **>1 comparable take**, fire **one** "run done"
  notify, and **auto-publish** per the rule below.
- **Bounded auto-publish (may cross Version→Publish):** only when `run.type ∈ {control-pass, upscale, comp}`
  **and** the run expanded to **exactly 1 version** — nothing to choose. Creative sweep-shapes never
  auto-publish (picking a take is judgment). The output **lands as a Version, then is auto-promoted**.
- **Wired chains (may start new Runs) on `PublishRecorded`:** only **judgment-free** transitions —
  `(trigger + Role/tag match) → a fully-pinned Run recipe` (default Spell, fixed params), e.g. a tagged 720
  Hero → its depth `control-pass`. Any runtime choice disqualifies it (→ human / Ringmaster). A **short
  explicit registry**, not a workflow graph.

Filled today by a **thin Python worker** — Postgres `LISTEN/NOTIFY` over a **durable `events` outbox**
(ADR 0019), a `FLOWS[run.type]` reaction table, and a `CHAINS` registry keyed on Role/tag. **Actions are
idempotent** (delivery is at-least-once). It **graduates** to a real workflow engine (Prefect / Temporal /
Windmill / …) only when hand-rolled retries/observability earn it — the **Spell → Skill** rule (ADR 0012).
_Avoid_: collapsing the Roustabout into the Submitter; naming this role after a tool ("Griptape" is a
candidate **tool**, not this role); putting orchestration in the **DB**; letting a chain make a runtime
choice (that is the Ringmaster's).

### Ringmaster
The **agent floor of orchestration — the show-director (later).** Looks at outputs and **decides**
(quality, which take to promote, what to do next), drives multi-step flows, and talks to Andy. The role
the future **Hermes** agent (earmarked for **Ramdass**) plays once the structure exists. Sits **above**
the Roustabout and is **deferred** — only the Roustabout exists today. Tooling is **TBD**: **Griptape**
(an LLM/agent framework) or the **Claude Agent SDK** are the candidates (ADR 0012). AYON's event-driven
**Workflows** is a *reference design* for this side, not an adopted system (ADR 0008).
_Avoid_: pushing Ringmaster (judging) logic down into the Roustabout or the Submitter; putting
orchestration in the **DB**.

### Orchestration events (`VersionRecorded` / `PublishRecorded`)
The two **events** the **Submitter** emits and the **Roustabout** consumes — the seam between the writer and
the deterministic floor (ADR 0018). **`VersionRecorded`** = *a take landed* (its `address` is written —
ADR 0013); drives the Roustabout's per-take + per-run-barrier reactions. **`PublishRecorded`** = *a Publish
was created* (by auto-publish **or** a human promote); drives **wired chains**, matched on the Publish's
**Role/tag**. Both are written as durable **`events` outbox** rows in the same transaction as the row they
describe, then `NOTIFY`-ed for low latency (ADR 0019) — so the event is never lost if the Roustabout is
down, and the Roustabout's handlers are **idempotent** (at-least-once delivery).
_Avoid_: treating the `NOTIFY` as the source of truth (the durable `events` row is); emitting before the
artifact exists.

### Run
One **Submit event** logged against a Shot — the unit the Submitter records to Mckenna's DB. Captures
the **recipe** — `bindings` (all inputs by Role), `params` (fixed base knobs), and a type-specific
**`spec`** (the operation/variation; ADR 0016) — plus request-id and cost, and produces **one or
more Versions** (the Submitter **expands** the `spec` into them). Has a **`type`** — the single dispatch
key the **Roustabout** branches on (ADR 0014):
`seed-sweep`, `prompt-variation`, `xy-plot`, `refine` (gen sweep-shapes) plus the operation types `comp`,
`upscale`, and `control-pass`. **Orthogonal to** a Version's **`stage`** (`render` / `upscale` / `comp`),
which only records which `versions/<stage>/` bucket a take lands in (`comp`→comp, `upscale`→upscale, the
rest→render). A Run also logs non-gen-AI Skill executions (e.g. a `control-pass` Run produces a control
**Publish** — depth/canny/openpose/matte).
_Avoid_: **Cast** (flavor — the verb is **Submit**).

### Submit
The **verb** for sending a **Run** to a model/farm (API, Comfy, or Flamenco). The **Submitter** does
this. _Avoid_: using "Submit" for the **client** gate — that act is **Deliver** (see *Delivery*).

### Recipe
How a take was made, stored in **two parts by level** (ADR 0007):
- **Authoring level — on the Run.** Shared, sweep-wide intent recorded once: the **Template**
  reference, the `{asset → pinned Publish/Import, role}` bindings (all inputs), model/tier/mode, fixed
  **params**, and the type-specific **`spec`** (operation/variation — axes, seeds, variants, …; ADR 0016).
- **Resolved level — on each Version.** A **frozen Submission Prompt + resolved params** — the exact
  payload actually sent — stored as an **immutable value object** (JSONB), sufficient on its own to
  reproduce the take even if the Template is later rewritten.
A Version's "full recipe" = pointer to its Run's authoring recipe + its own frozen submission + delta.

### Manifest
The **thin** per-Project map header (`manifest.json` at the Job root): Project **identity**
(`client_code`, `job_code`, `title`), the logical **`base_path`**, and **pointers** tying Git ↔ the
Huxley store ↔ Mckenna's DB (`db_project_id`). It holds **no provenance** — all Runs/Versions/
Publishes/Deliveries live in the **DB**, and the Episode/Sequence/Shot/Asset structure is discovered
by walking the deterministic tree (ADR 0003). *(Exception, ADR 0020: a **Sequence** also carries a small
DB **config** record for its shared defaults — but its **existence** is still the tree's folder, not the
row; the DB stores the Sequence's *settings*, never the authority on what Sequences exist.)* Versioned by an integer **`manifest_version`** (bump on
breaking change). Schema: `schemas/manifest.schema.json`.

### Asset
A **versioned input used to make the gen-AI video**, bound into a Shot in a **Role**. Its content is
either a **Publish** (an internal gen-AI output re-entering the pipeline) or an **Import** (an
external file). Lives **flat** and **descriptively named** in one of two scopes (`<Job>/assets/`
shared, `<Shot>/assets/` shot-specific — see *Asset scoping*). An Asset has **versions**; the system
resolves its **resolved content** (the **Publish**/Import currently selected) when writing prompts and
wiring workflows. *How* a **Version** uses an Asset is its **Role**.
_Avoid_: calling an Asset's resolved content its "promoted" version — **promote** is reserved for the
**gate verb** (Version→Publish→Delivery). An Asset's content may be a Publish (which *did* cross a gate)
or an Import (which never does), so the neutral term **resolved** covers both — and sidesteps the
**promote/prompt** look-alike.
_Avoid_: using "Asset" for a CG **entity** (a modeled character/environment) — reserved, unused for now.

### Reference / Role
**Reference** is the doorway concept (locked §7): an **Asset entering the AI room** in a **Role**.
A **Role** is a property of the **binding** — the use of an Asset by a specific Shot/**Version** —
**not** of the Asset itself: the same Asset can be **First-Frame** in one Shot and a plain reference
in another. Values: **First-Frame**, **Last-Frame**, **Lipsync-Dialog**, **Character-Sheet**,
**Depth-Pass**, **Canny**, **OpenPose**, **Matte** (the per-kind control-pass Roles — ADR 0017),
**Style**, **Plate/Driver**, **Source** (the Publish an op like upscale/refine/comp
consumes), **Comp-Input**, … Role is the **wiring key** — it tells the Submitter both how to reference
the Asset in the prompt **and** which Comfy node / API slot to feed it into.
Recorded as a binding `{asset → pinned Publish/Import, role}` on the **Version's recipe** — **not** a
folder.
_Avoid_: making Reference or Role a folder; bind by role in **data**.

### Asset scoping
Assets live in one of **two physical homes** (folders), but have **three binding scopes**:
- **`<Job>/assets/`** — everything shared across shots: characters, environments, concept &
  character sheets, master audio, fonts.
- **`<Shot>/assets/`** — shot-specific inputs only: first-/last-frame images, the shot's plate,
  shot-only references.
- **Sequence scope** *(no folder — ADR 0020)* — an Asset whose **file** still lives flat in
  `<Job>/assets/`, but whose DB **scope=`sequence`** auto-binds it to **every Shot in one Sequence**
  (a Shot can override). It is a **binding scope**, not a new folder — consistent with "scope/Role is
  metadata, not folders."

There is **no** Episode-level asset folder and **no Sequence asset *folder***: a Sequence-shared Asset
still lives flat in `<Job>/assets/`; only its **binding scope** says "all of SALEM's Shots." If an asset
is shared beyond one Shot, it goes in `<Job>/assets/`. Shot **outputs** (Versions, Publishes) are **not** Assets and live
in their own per-Shot subfolders. Assets are stored **flat** and named **descriptively** for
what they are (e.g. `main character sheet`, `desert environment`) — not bucketed by type or role.
An Asset's content is a **Publish** or an **Import**; the file in `assets/` is its **resolved**
content (the currently-selected Publish/Import — see *Asset*), and its Role is recorded per-use on
the **Version's recipe**, not in the folder.

### Project folders
The named buckets inside a Project (Job). Full canonical tree in **ADR 0003**.
- **`manifest.json`, `CONTEXT.md`** *(Job root)* — the Project's map and its local glossary/notes.
- **`_ops/`** *(Job root)* — operational, non-creative: `scripts/` (PS1/automation), `logs/`
  (local run & job logs), `config/` (tool config), `jobs/` (Flamenco submission files).
- **`assets/`** *(Job root)* — shared cross-Shot Assets (see *Asset scoping*).
- **`editorial/`** *(Job root)* — Premiere/AE cut assembly; job-wide finishing.
- **`<Episode>/deliverables/`** — the per-Episode final handoff to the Client.
- **Per Shot:** `assets/` (shot-specific input files), `work/` (editable DCC scenes: `blender/`,
  `nuke/`), `versions/` (all takes from Runs, staged: `render/` `upscale/` `comp/`; recipe attached),
  `publishes/` (internal-promoted, `p###`, stable + pointer back). See *Version*, *Publish*, *Delivery*.
  A **Delivery** is a Publish promoted across the client gate (record + client `v#`), assembled into
  the Episode `deliverables/`.

### Version
One **take/output** a **Run** produces — a single render, seed, or sweep entry. Numbered per Shot
(`v001`, `v002`, …). Lives in `<Shot>/versions/<stage>/` (stage = `render` / `upscale` / `comp`).
Carries its **full recipe** (how it was made: prompt, seed, model, tier, mode, resolution, and the
Asset→Role bindings). Its address is **ephemeral** (model output URLs rot) — **nothing downstream
may point at a Version**. Per ADR 0007 a Version also stores an **immutable frozen Submission Prompt +
resolved params** (its self-contained reproduction payload); the rest of its recipe lives once on the
parent Run.
_Avoid_: **Generation** (use *Version* — the VFX term; this is a deliberate divergence from the prior
UL, see ADR 0005).

### Publish
A **Version promoted** past the **internal** review gate to a **stable, canonical, downstream-safe**
address. Lives in `<Shot>/publishes/`, numbered in its **own** namespace (`p001`, `p002`, …) — it does
**not** inherit the Version's number. **Thin**: identity + a **pointer back** to its source Version
(recipe never duplicated). Re-promoting after a note creates the **next Publish** (`p002`…). A Publish
is the **only** thing downstream contexts (upscale, comp, editorial, delivery) may reference — and when
it **re-enters** another Shot as input it does so as an **Asset** in a Role.
_Avoid_: "Select" (legacy `*Selects` folders) — those are Publishes.

### Deliver / Delivery
**Deliver** is the **verb** for promoting a **Publish** across the **client** gate. A **Delivery** is
the result — a Publish blessed for the client, numbered in a **client-facing** namespace (`v1`, `v2`, …)
that **resets at the gate**, so the client's first sight is **v1** regardless of how many internal
Versions/Publishes preceded it. A Delivery is a **special kind of Publish** (it points back to its
source Publish); the delivered file is assembled into the Episode `deliverables/` package.
_Avoid_: "Submit to client" — that act is **Deliver** (Submit is the *farm* verb).

### Lineage
The **chain of pointers** linking **Delivery → Publish → Version → Run** (and **Asset → Publish/Import**).
Because each gate has its **own** numbering, **lineage — not numbers — carries provenance**: "what were
the earlier takes?" is answered by walking the pointers, never by a number leaking across a gate. (This
is the §6 "lineage face": relations, not inlined data.)

### Import
An **external file** brought into the pipeline that was **not** produced by our gen-AI (client plate,
sourced audio, stock, scan). The **external sibling of a Publish**: versioned and addressable the
same way, and usable as an **Asset** in a Role. The Publish-vs-Import distinction (internal *has* a
source Version; Import does not) is what keeps provenance honest.

### Seed Sweep
A **Run type**: N **Versions** across seeds (or params) for variation. A set of **Versions**, never of
Publishes. Other gen Run types: `prompt-variation`, `xy-plot`, `refine`; operation types: `comp`,
`upscale`, `control-pass` (full enum in ADR 0014, amended by ADR 0017).

### Control Pass
A **Run type** (`control-pass`) that derives a **control/structure reference** from a Source plate/frame
and produces a **Publish** bound downstream in a **per-kind Role**. The kinds — **depth, canny, openpose,
matte, …** — are **flavors**: each is a **Spell** named by `spec.method` (`depthcrafter-bw20`,
`depthcrafter-anyline-combo`, `canny`, `openpose`, …). **One run.type, many Spells** (ADR 0017): the type
is the dispatch family, the Spell is the craft, the Role is the wiring slot. Scope is control/structure
maps only — **audio** prep and **creative assets** are not control-passes.
- **Depth Pass** — the depth flavor: a depth-map reference for gen-AI video; the first hardened control
  craft (the `depth-pass` **Skill**, which implements the depth family of `control-pass` methods).
_Avoid_: a separate `run.type` per control kind — they share `control-pass` and vary by Spell/Role.

### Fleet
The whole networked system of machines + storage, joined over **Tailscale**. Canonical
per-machine specs (hardware, OS, Tailscale IP, status) live in the **Fleet DB in Notion**
([link](https://www.notion.so/d527c0568d0b4d3db4c228dc58a7c503)); CONTEXT.md records only
each machine's *role*. Current machines:

- **Watts** — Andy's primary **workstation** (Windows 11). Where Projects are edited.
- **Leary** — mobile **workstation** (Windows); used when Andy works away from Watts.
- **Huxley** — the big-storage **renderer** (Unix) and the **canonical Project store**
  (the shared Fleet projects area; see *Project store*).
- **Mckenna** — the **Flamenco controller** and **DB host** (Unix). Hosts the databases the
  Submitter writes Runs to, and the Flamenco controller that dispatches jobs. **Does not
  render.** Shares only a small `tools` directory.
- **Ramdass** — Mac mini (macOS), currently **idle**; earmarked as a future **Hermes**
  agent — the one that plays the **Ringmaster** role — that will drive these flows once the
  structure is built. Not yet wired in.

### Flamenco
The render farm manager. Its **controller** runs on **Mckenna** and **dispatches** Blender
render/gen jobs to the **renderer** on **Huxley**; outputs land in Huxley's render output
area. Where heavy render jobs are submitted and tracked.

### Project store
The single canonical home for all Project files, living on **Huxley** and served to the rest
of the Fleet over Tailscale/10GbE. One authoritative copy — not a per-workstation original
plus mirrors. The renderer (Huxley) reads Projects with local disk access; workstations
(Watts/Leary) edit them over the network.

### Provenance store
The **system of record for all provenance**: a thin **PostgreSQL** DB we own, in our own UL, on
**Mckenna** (ADR 0008). Tables are the UL nouns — `projects`, `runs`, `versions`, `publishes`,
`deliveries`, `assets`, `bindings` — with a **JSONB frozen-submission** column on `versions` (ADR 0007).
**Lineage = FK pointer edges**, walked with recursive queries; gate counters stay per-gate. `db_project_id`
is a `projects` row UUID; the **`projects` table is the project index**. Each machine finds the DB via the
**Postgres DSN in Fleet config** (same pattern as `base_path`). **Notion is a one-way read view, never the
source of truth**; the legacy "Video Generations log" migrates in.
_Avoid_: treating Notion as truth; putting orchestration (proxy / next-step logic) in the DB — that is
the **Roustabout**'s job (Branch 5), fired by a `VersionRecorded` event.

### base_path
A Project's (Job's) root location, stored in the **Manifest** in **platform-neutral** form
(a logical root + `<client_code>/<job_code>`) and **resolved per-machine** to a real path —
because the Fleet is mixed OS (Windows/Unix/macOS), a raw `D:\…` or `/…` string would be wrong
on half the boxes. The canonical store is on **Huxley** under a shared parent (the `io/common`
tree, alongside renders). Windows reaches it by UNC over Tailscale (`\\huxley\…`); Huxley is
also reachable by `ssh andy@huxley`. Resolution per machine:
- Logical (in Manifest): `fleet:/projects/<client_code>/<job_code>/`
- Huxley (Unix, canonical): `/nvme1/comfyui/io_common/projects/<client_code>/<job_code>/`
- Watts / Leary (Windows): `\\huxley\io_common\projects\<client_code>\<job_code>\` (Samba **`io_common`** share)

Resolved per-machine via Fleet config (`~/.fleet/config.toml` → `[paths].projects_root`). **Note:** ADR-0002
was decided but not yet executed — real projects still sit on Watts-local `W:\Projects`; new projects
scaffold to Huxley, and the existing ones migrate over (tracked with the ADR-0003 legacy migration).

### Context (DDD)
A bounded area that speaks one shared language, documented in a `CONTEXT.md`.
Right now the whole system is one Context; split into a context-map only if it grows.

### ADR — Architectural Decision Record
A short markdown file in `/adr` capturing a **non-obvious, hard-to-reverse decision**
and *why*. Write one only when a choice is surprising-without-context or has real
trade-offs downstream.

---

## Relationships & rules

- A **Spell** may invoke one or more **Skills**; a **Skill** never depends on a Spell.
- A **Spell** graduates to a **Skill** when invoked frequently.
- **Skills** live in Git (this repo, `skills/`). **Spells** + **Templates** live in the **Spellbook**
  (`spellbook/` in this same repo — ADR 0009); a **Spell graduates** by moving into `skills/`.
- The **Submitter** writes **Runs/Versions** to the **Postgres provenance store on Mckenna** and
  dispatches renders to **Flamenco**. Writing a Version emits **`VersionRecorded`**; the **Roustabout**
  (Branch 5) renders the proxy and writes the pointer back — **orchestration never lives in the DB**.
- One **Submit** → a **Run** → one or more **Versions**; promoting a Version (internal gate) makes a
  **Publish**; **Deliver**ing a Publish (client gate) makes a **Delivery**. Each gate numbers
  independently (`v###` → `p###` → client `v#`); **lineage pointers** carry provenance, not numbers.
- **Downstream references only Publishes/Deliveries**, never a **Version** (ephemeral address).
- **Storage rule:** code / skills / docs / decisions → **Git**. Heavy binary media → the
  **Project store on Huxley**, rendered via **Flamenco** (controller on Mckenna → renderer
  on Huxley), referenced by the **Manifest**. Never mix the two.

---

## Open questions (to resolve via grilling / ADRs)
- **Orchestration** — split into **two floors**: **Ringmaster** (agent, later; Hermes plays it) over
  **Roustabout** (deterministic worker, now — a thin Python worker), joined to the Submitter at
  `VersionRecorded`; **Griptape demoted** to a Ringmaster-floor candidate. ✅ (→ ADR 0010, amended by 0012)
- **Manifest schema** — thin map header, integer `manifest_version`, provenance in DB. ✅ (→ ADR 0006)
- Where does the **Spellbook** physically live once migrated — a folder in this repo,
  a separate repo, or stays in Notion with a sync? (→ decide early)
- Naming: confirmed **"skill"** for Claude Code skills, **"spell"** for Spellbook entries. ✅
- **Project store** lives on **Huxley**; `base_path` is platform-neutral + resolved per-machine. ✅ (→ ADR 0002)
- **Project structure** — hierarchy, shot-centric layout, two-tier assets, `_ops/`, per-Episode deliverables. ✅ (→ ADR 0003)
- Deferred config: Huxley `io/common` prefix (`/nvme1/comfyui/io_common`) + Windows share name
  (`io_common`) — **resolved** (Session 2). Still open: the per-machine **fleet repo clone path**
  (logical root resolved per workstation, like `base_path`).
- Whether the **Episode** token appears in the Shot code — **resolved:** included (`JOB_EP_SEQ_SHOT`,
  `AWA_EP01_SALEM_010`) because Sequence names recur across Episodes. ✅ (→ ADR 0015)
- **Reconciled vs. prior UL handoff:** spine terms (Episode/Sequence), Generation/Publish split,
  Asset-over-Reference + Role-as-metadata. ✅ (→ ADR 0004)
- **Artifact & versioning model** — Run/Submit, Version (←Generation), Publish `p###`,
  Deliver/Delivery (client gate), Import, Lineage; gated namespaces + pointer provenance. ✅ (→ ADR 0005)
- **Spellbook holds Spells (recipes) + Templates (verified prompt patterns of Blocks)**; Brief →
  Template → Submission Prompt. ✅ (extends ADR 0001) — Template vetting is aspirational (unvetted today).
- Micro to-confirm: term for unvetted Block candidates = **variant** ✅; "function" = Template→**mode**
  (`t2v`/`i2v`/`r2v`), Block→**purpose** (camera/style/lighting/motion) ✅.
- **Branch 4 — Provenance DB** — own thin **Postgres on Mckenna**; project index = `projects` table;
  `db_project_id` = row UUID; Notion → one-way view. ✅ (→ ADR 0008)
- **Recipe storage** — hybrid: authoring recipe on the Run + frozen Submission Prompt per Version. ✅ (→ ADR 0007)
- **Invoices / commercials** — a **separate bounded context** off `Delivery`; site in a later branch
  (fine in Notion keyed off Delivery IDs until then). Parked.
- **Branch 3 — Spellbook location** — a `spellbook/` folder in **this repo**, distributed by the Git
  remote (clone + pull per machine); Notion demoted. ✅ (→ ADR 0009)
- **Branch 5 — Orchestration** — two floors (**Ringmaster** agent / **Roustabout** worker); Roustabout =
  thin Python worker now (graduate-when-earned); Griptape reserved as a Ringmaster candidate. ✅ (→ ADR 0010, 0012)
- **Session 2 reconciliation (implementation):** ADR-0003 is **confirmed the target** — the live
  hand-made projects (e.g. `WBTV/AWA`) are **non-conforming legacy** (task-centric folders like
  `AI_Frames/`,`AI_Renders/`; flat `v##`-in-filename takes; Notion log), to be **migrated, not
  emulated**. The existing **fal_runner** (`D:\Tools\fal_runner\submit.py` + per-shot `run_*.ps1` +
  `*.toml` + Notion) and **comfy_runner** predate the grilling: they work when run by hand but are
  **not aligned** with ADR-0003 or this UL, and will be **realigned** (paths → ADR-0003 tree;
  provenance → Postgres). ✅
- **Runner** *(to formalize — not yet an ADR):* a **provider-specific backend the Submitter dispatches
  to** (fal, Comfy, …) — distinct from the one atomic **Submitter**. Each legacy runner is today a
  mini-submitter, to be folded behind the Submitter. **New:** add a **Magnific** runner
  (https://docs.magnific.com/introduction) for AI upscale/enhance → output in `<Shot>/versions/upscale/`.
- **Control passes generalized** — `depth-pass` run.type → **`control-pass`** (depth/canny/openpose/matte =
  one type, flavor = Spell via `spec.method`, per-kind Role; audio + creative assets out of scope). ✅
  (→ ADR 0017, amending 0014/0016)
- **Roustabout `FLOWS`** — two-tier reactions (per-take proxy/log + per-run barrier: contact-sheet/notify/
  auto-publish); auto-publish bounded to `control-pass` + single-output `upscale`/`comp`; wired
  judgment-free chains on a `(Role/tag → pinned Run recipe)` registry; second event `PublishRecorded`;
  delivery = `LISTEN/NOTIFY` + durable `events` outbox, idempotent handlers. ✅ (→ ADR 0018, 0019)
- **Branch 6 — real control-pass methods** — pull the actual steps for each flavor Spell (the depth ones
  first) to replace the `depth-pass` SKILL.md TODOs; migrate the variant recipes into `spellbook/spells/`.
  **Next.**
- **Implementation deferred (from ADR 0018/0019):** the `events` outbox table (migration
  `0003_events_outbox.sql`); the notify target/channel (Notion view / a feed); idempotency keys for
  auto-publish + chains; the concrete `CHAINS` registry contents (first entry: Hero → depth `control-pass`).
