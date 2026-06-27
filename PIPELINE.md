# PIPELINE.md — Fleet Production Pipeline (canon flowchart)

> Conforms to **CONTEXT.md** (ubiquitous language) and **ADR 0002–0016**. Ground-truth for Claude Code
> implementation. Read alongside `CONTEXT.md` and `HANDOFF.md`.
>
> Spine: **Submit → Run → Version (`v###`) → Publish (`p###`) → Delivery (client `v#`)**. Numbers
> **reset at each gate**; **lineage pointers** (not numbers) carry provenance (ADR 0005). The Manifest is
> **one per Job**, thin, and holds **no** provenance — all of it lives in **Postgres on Mckenna**
> (ADR 0006/0008).
>
> Three views: **View 1** main Shot flow (Brief → Delivery), **View 1b** the generalized Asset Production
> sub-flow (supervisor-only), **View 2** system/provenance (who writes what, when).

## Shapes & classes

- `([ ])` event/terminal · `[ ]` process/act · `{ }` review gate · `[( )]` datastore.
- **GenAI** = a Run that invokes a model · **Skill** = a hardened deterministic Skill (e.g. `depth-pass`) ·
  **Spell** = working-layer recipe/Template not yet graduated · **Import** = external input ·
  **Publish/Delivery** = gated artifacts · **sys** = Submitter / Roustabout / create-project.

## Key rules baked into the graph

- **Every gen step is the same loop:** author a Submission Prompt from a Spellbook **Template** →
  **Submit → Run → Version(s) → (review gate) → Publish**. The main Shot sweep adds a **second**, client
  gate (**Deliver**); **Assets do not** — they are **supervisor-approved only** (ADR 0005 audiences:
  Version=internal, Publish=supervisor, Delivery=client).
- **Only a Publish (internal) or an Import (external) may be bound to a Role — never a bare Version.**
  Internal assets (Character-Sheet, First/Last-Frame, Depth-Pass) must be **Published** first; external
  Imports (client plate, stock) bind directly.
- **Assets, like Shots, run the full Version→Publish loop and log all provenance to the DB** — each asset
  type has its **own Spell + Template + a Run-specific Submission Prompt**; every Version, Publish, and
  binding is written to Postgres on Mckenna.
- **No per-asset manifest.** The handoff to the next step is the **Publish pointer (`p###`) + DB resolve**;
  the manifest is one-per-Job (ADR 0006).

---

## View 1 — Main Shot Flow (Brief → Delivery)

```mermaid
flowchart TD
    %% ===== VIEW 1 — MAIN SHOT FLOW =====
    %% Client > Job > Episode > Sequence > Shot. Submit->Run->Version->Publish->Delivery.

    CP["create-project<br/>scaffold ADR-0003 tree · INSERT projects row · write thin manifest"]:::sys
    BRIEF(["Brief — human creative request (intent)"])
    CP --> BRIEF

    %% ---- Author the Shot's Submission Prompt (from the Spellbook) ----
    TPL[("Shot Template (Spellbook)<br/>verified prompt pattern · built from Blocks")]:::book
    AGENT["Author Submission Prompt<br/>agent makes Template task-specific from the Brief"]:::ai
    TPL --> AGENT
    BRIEF --> AGENT

    %% ---- Required input Assets (each = the Asset Production sub-flow, View 1b) ----
    PLATE["Plate / Driver<br/>Import (client plate · stock · scan) — binds directly<br/>OR a self-gen driver as a Publish (normal Run→Version→Publish loop)"]:::imp
    SHEET["Character-Sheet<br/>Asset Production sub-flow (Spell)"]:::ai
    FRAME["First / Last-Frame<br/>Asset Production sub-flow (Spell)"]:::ai
    DEPTH["Depth-Pass<br/>Asset Production sub-flow (depth-pass Skill + variant Spells)"]:::skill
    LIPSYNC["Lipsync-Dialog<br/>Asset Production sub-flow (Spell) — AI-gen VO/performance (Publish)<br/>OR sourced VO as an Import — binds directly"]:::ai
    BRIEF -->|"required inputs"| PLATE
    BRIEF -->|"required inputs"| SHEET
    BRIEF -->|"required inputs"| FRAME
    BRIEF -->|"required inputs"| DEPTH
    BRIEF -->|"required inputs"| LIPSYNC

    %% ---- Bind Assets in Roles (Publish XOR Import only) ----
    BIND["Bind Assets in Roles<br/>ONLY a Publish (internal) or Import (external) — never a bare Version<br/>role = wiring key: prompt ref + Comfy node / API slot"]
    AGENT --> BIND
    PLATE -->|"Plate Role (Import or Publish)"| BIND
    SHEET -->|"Character-Sheet Role (Publish)"| BIND
    FRAME -->|"First / Last-Frame Role (Publish)"| BIND
    DEPTH -->|"Depth-Pass Role (Publish)"| BIND
    LIPSYNC -->|"Lipsync-Dialog Role (Publish or Import)"| BIND

    %% ---- Submit -> Run -> Versions ----
    SUBMIT["Submit (via Submitter)"]:::sys
    BIND --> SUBMIT
    RUN["Run — type: seed-sweep | prompt-variation | xy-plot | refine<br/>authoring recipe: bindings (all inputs by role) + params + type-specific spec (ADR 0016) -> DB<br/>Submitter validates spec vs Template knobs, then expands -> Versions"]
    SUBMIT --> RUN
    VERS["Versions v001..v0NN<br/>stage: render / upscale / comp<br/>frozen Submission Prompt (immutable) -> DB"]:::ai
    RUN --> VERS

    %% ---- Internal (supervisor) gate ----
    IREVIEW{"Internal review (supervisor) — which take?"}
    VERS --> IREVIEW
    IREVIEW -->|"promote (internal gate)"| PUB["Publish p001..<br/>stable · downstream-safe · pointer back -> DB"]:::pub
    IREVIEW -->|"note"| NTRI{"Note triage — by type"}

    %% ---- gen-AI video Publish re-enters downstream as an Asset in a Role ----
    PUB -.->|"re-enters as Asset content"| BIND

    %% ===================== FINISH: comp fork -> approval -> up-res -> QC -> deliver =====================
    %% ---- Comp fork (after the gen-AI video Publish) ----
    COMPQ{"Comp needed?"}
    PUB --> COMPQ
    COMPIN["Comp inputs<br/>other Publishes + Assets + Imports (reference)"]
    COMP["Comp Run — Nuke (Spell)<br/>type: comp · stage: comp · .nk in work/nuke/<br/>combine multiple inputs"]:::tool
    COMPQ -->|"yes"| COMP
    COMPIN -->|"bound by Role"| COMP
    COMP --> COMPV["Comp Versions — versions/comp/ -> DB"]:::tool
    COMPV --> CSUP{"Supervisor review (comp)"}
    CSUP -->|"note -> comp refine"| COMP
    CSUP -->|"promote (internal gate)"| CPUB["Comp Publish p### -> DB"]:::pub

    %% ---- Client gate = a Delivery (every client send is client-versioned) ----
    DELIVER["Deliver (client gate)"]:::sys
    COMPQ -->|"no — deliver as-is"| DELIVER
    CPUB --> DELIVER
    DELY["Delivery — approval round<br/>client v# (first sight = v1)"]:::del
    DELIVER --> DELY
    CREVIEW{"Client approval"}
    DELY --> CREVIEW
    CREVIEW -->|"note"| NTRI
    CREVIEW -->|"approved"| UPRES["Up-res Run — Magnific / Topaz<br/>type: upscale · stage: upscale -> DB"]:::tool

    %% ---- Up-res -> QC -> final master Delivery ----
    UPRES --> UVERS["Up-res Versions — versions/upscale/ -> DB"]:::tool
    UVERS -->|"promote (internal gate)"| UPUB["Up-res Publish p### -> DB"]:::pub
    UPUB --> QC{"QC — on the up-res Publish"}
    QC -->|"fail: comp-fix"| COMP
    QC -->|"fail: note -> stage"| NTRI
    QC -->|"pass"| DELIVERF["Deliver final master (client gate)"]:::sys
    DELIVERF --> DELYF["Delivery — final master<br/>client v#"]:::del
    DELYF --> DONE(["Delivered<br/>assembled into Episode deliverables/"])

    %% ---- Revision routing: note type -> which Asset/Role or Template to swap (refine Run) ----
    NTRI -->|"design"| SHEET
    NTRI -->|"lighting"| FRAME
    NTRI -->|"lip-sync / dialog"| LIPSYNC
    NTRI -->|"take / performance"| PLATE
    NTRI -->|"motion / prompt — video prompt revision"| AGENT

    classDef sys fill:#1f2a44,stroke:#4866b0,color:#eaf0ff;
    classDef ai fill:#2a1f44,stroke:#7a4fd0,color:#f1eaff;
    classDef skill fill:#143028,stroke:#2f8f6f,color:#e6fff5;
    classDef tool fill:#22302b,stroke:#5f8f76,color:#e6fff2;
    classDef book fill:#3a2f12,stroke:#b08a2f,color:#fff6e0;
    classDef imp fill:#3a1f1f,stroke:#b05050,color:#ffe9e9;
    classDef pub fill:#16304a,stroke:#3f86c4,color:#e6f3ff;
    classDef del fill:#103a24,stroke:#36a866,color:#e3ffe9;
```

> **Finish reading.** A **gen-AI video Publish** either delivers **as-is** or goes through a **Comp Run**
> (Nuke; `type: comp`, `versions/comp/`, `.nk` in `work/nuke/`) that combines multiple Publishes/Assets/
> Imports. Whatever is sent to the client crosses the **client gate** as a **Delivery** (the approval round
> is `v1`, revisions `v2…`). On approval, **Up-res** (`versions/upscale/`) → **QC** on the up-res Publish:
> **pass → Deliver** the final master (next client `v#`); **fail →** a **comp-fix** (back to the Comp Run)
> or a **note** routed to the corresponding upstream stage (video prompt revision, new first/last-frame,
> character-sheet, etc.). Comp and Up-res are themselves **Runs** through the Submitter — every Version and
> Publish logs to Postgres.

---

## View 1b — Asset Production sub-flow (generalized; supervisor-only)

Each internal Asset — **Character-Sheet**, **First/Last-Frame**, and **Lipsync-Dialog** (Spells), and
**Depth-Pass** (a hardened `depth-pass` Skill plus variant Spells like `depthcrafter-bw20`) — instantiates
this one loop. It is the
same Submit→Run→Version→Publish spine as a Shot, **minus the client gate**: an Asset is **approved by the
supervisor (Andy) only**, then its **Publish** is what gets bound into a Shot Role.

```mermaid
flowchart TD
    %% ===== VIEW 1b — ASSET PRODUCTION SUB-FLOW (supervisor-only) =====
    ABRIEF(["Asset Brief — intent for this input"])
    ATPL[("Asset Template + Spell (Spellbook)<br/>per asset-type · own prompt pattern / Blocks")]:::book
    AAUTH["Author Submission Prompt<br/>asset-specific prompt for this Run"]:::ai
    ATPL --> AAUTH
    ABRIEF --> AAUTH
    AAUTH --> ASUB["Submit (via Submitter)"]:::sys
    ASUB --> ARUN["Run — INSERT run + bindings + authoring recipe -> DB"]
    ARUN --> AVERS["Versions v### — frozen submission -> DB"]:::ai
    AVERS --> ASUP{"Supervisor review (Andy)<br/>INTERNAL only — NO client gate"}
    ASUP -->|"note -> refine Run"| ARUN
    ASUP -->|"promote (internal gate)"| APUB["Publish p### — INSERT publish · pointer back -> DB"]:::pub
    APUB --> AROLE(["Bind to a Role in a Shot (View 1)<br/>only a Publish or Import may hold a Role"])

    classDef sys fill:#1f2a44,stroke:#4866b0,color:#eaf0ff;
    classDef ai fill:#2a1f44,stroke:#7a4fd0,color:#f1eaff;
    classDef book fill:#3a2f12,stroke:#b08a2f,color:#fff6e0;
    classDef pub fill:#16304a,stroke:#3f86c4,color:#e6f3ff;
```

| Asset type | Maturity | Spellbook entry | Resulting Role |
|---|---|---|---|
| **Character-Sheet** | Spell (working layer) | own Template + Spell | Character-Sheet |
| **First / Last-Frame** | Spell (working layer) | own Template + Spell | First-Frame / Last-Frame |
| **Lipsync-Dialog** | Spell (working layer) | own Template + Spell (AI VO); sourced VO binds as an Import | Lipsync-Dialog |
| **Depth-Pass** | **Skill** (hardened spine) + variant Spells (`depthcrafter-bw20`, `depthcrafter-anyline-combo`) | spine in `skills/`, recipes in `spellbook/spells/` | Depth-Pass |

A Spell **graduates into a Skill** when invoked often enough (ADR 0001/0009) — that is why depth-pass is
already a Skill and the other two are not yet.

---

## View 2 — System / Provenance (who writes what, when)

```mermaid
flowchart LR
    %% ===== VIEW 2 — SYSTEM / PROVENANCE =====

    subgraph GIT["Git repo (fleet_skills) — code/decisions"]
        SPB[("Spellbook<br/>spells/ · templates/ · blocks/")]:::book
        SKILLS[("Skills<br/>create-project · depth-pass · submitter")]:::sys
    end

    subgraph WS["Workstation (Watts / Leary)"]
        MAN["manifest.json (THIN, one per Job)<br/>identity + base_path + db_project_id<br/>NO provenance · written ONCE at create-project"]
    end

    SUBM["Submitter (atomic)<br/>ingest · INSERT run/version · dispatch<br/>on render-complete: write address + emit VersionRecorded"]:::sys

    subgraph MCK["Mckenna — DB host + Flamenco controller"]
        subgraph PG["Postgres provenance store (system of record)"]
            T_PROJ["projects"]
            T_RUN["runs (authoring recipe: template_ref, model/tier/mode, params)"]
            T_VER["versions (v### · frozen_submission JSONB · ephemeral address)"]
            T_PUB["publishes (p### · ptr -> version)"]
            T_DEL["deliveries (client v# · ptr -> publish)"]
            T_AST["assets (scope job/shot · Publish XOR Import)"]
            T_BND["bindings (asset -> pinned Publish/Import, role)"]
        end
        FLAM["Flamenco controller — dispatch"]
    end

    subgraph HUX["Huxley — renderer + Project store"]
        REND["Blender / Comfy renderer"]
        STORE["Project store (heavy media)<br/>&lt;Shot&gt;/versions · publishes"]
    end

    RUNNER["Runner (fal / Comfy / Magnific)"]:::sys
    ROUST["Roustabout (deterministic, NOW)<br/>thin Python · LISTEN/NOTIFY · FLOWS[run.type]<br/>proxy · log · notify · chain (reacts to a landed take — no poll, no pointer-back)"]:::sys
    RING["Ringmaster (agent, LATER — deferred)<br/>judges quality / what next · Hermes @ Ramdass"]:::ai
    NOTION[("Notion — one-way READ view")]:::book

    %% create-project writes
    SKILLS -.->|"create-project: INSERT"| T_PROJ
    SKILLS -.->|"create-project: write"| MAN
    T_PROJ -->|"db_project_id (UUID)"| MAN

    %% submit path — same for Shot Runs AND Asset Runs (writer allocates per-gate counters; DB does NO orchestration)
    SPB -.->|"Template ref"| SUBM
    SUBM -->|"INSERT run + bindings"| T_RUN
    SUBM -->|"INSERT version(s)"| T_VER
    SUBM -->|"dispatch heavy"| FLAM
    SUBM -->|"dispatch model"| RUNNER
    FLAM --> REND
    REND --> STORE
    RUNNER --> STORE

    %% event seam — VersionRecorded fires only AFTER the take's output lands (address persisted); never at dispatch, never a DB trigger (ADR 0013)
    STORE ==>|"render-complete (Flamenco callback / sync Runner return)"| SUBM
    SUBM -->|"UPDATE versions.address (pointer back to landed output)"| T_VER
    SUBM ==>|"emit VersionRecorded — a finished take exists"| ROUST
    ROUST -->|"render proxy/thumbnail"| STORE
    ROUST -->|"chain next stage (calls Submitter)"| SUBM
    ROUST -.->|"needs judgment? escalate (later)"| RING

    %% gates
    T_VER --> PROMOTE["Promote (internal/supervisor gate) — Shots & Assets"]:::sys
    PROMOTE -->|"INSERT publish (p###)"| T_PUB
    T_PUB --> DELIVERV["Deliver (client gate) — Shot deliverable ONLY"]:::sys
    DELIVERV -->|"INSERT delivery (client v#)"| T_DEL

    %% lineage (FK pointer edges) + asset re-entry
    T_DEL -.->|"lineage"| T_PUB
    T_PUB -.->|"lineage"| T_VER
    T_VER -.->|"lineage"| T_RUN
    T_PUB -->|"re-enters as Asset content"| T_AST
    T_AST --> T_BND
    T_BND -.->|"authoring-level (on Run)"| T_RUN

    %% one-way read view
    PG -.->|"DB -> Notion (one-way)"| NOTION

    classDef sys fill:#1f2a44,stroke:#4866b0,color:#eaf0ff;
    classDef ai fill:#2a1f44,stroke:#7a4fd0,color:#f1eaff;
    classDef book fill:#3a2f12,stroke:#b08a2f,color:#fff6e0;
```

### What gets written to Mckenna's DB, and when

| Moment | Writes to Postgres (Mckenna) | Manifest |
|---|---|---|
| **create-project** | `INSERT projects` → returns `db_project_id` (UUID) | written **once** (thin, one per Job); `db_project_id` stored |
| **Submit** (a Run — Shot / Asset / **Comp** / **Up-res**) | `INSERT runs` (authoring recipe: `template_ref`, `params`, type-specific **`spec`** (ADR 0016); `type` ∈ seed-sweep / prompt-variation / xy-plot / refine / **comp** / **upscale** / **depth-pass**) + `INSERT bindings` (all inputs asset→role, incl. `Source` / `Comp-Input`) + `INSERT versions` (Submitter **expands `spec`** → one per take; `stage` render/upscale/comp, `frozen_submission` JSONB, **`address` NULL** until the take lands) | untouched |
| **Render completes** (Flamenco callback / sync Runner return) → **Submitter** | `UPDATE versions.address` (pointer back to the landed output) → **emit `VersionRecorded`** (ADR 0013) | untouched |
| **`VersionRecorded`** → **Roustabout** | *(no version-row write)* renders proxy/thumbnail, logs, notifies, chains the next stage | untouched |
| **Promote** (internal/supervisor gate — Shots, Assets, Comp, Up-res) | `INSERT publishes` (`p###`, `source_version_id`) | untouched |
| **Deliver** (client gate — approval round **and** final master, each a Delivery) | `INSERT deliveries` (client `v#`, `source_publish_id`) | untouched |
| **Asset registered / re-resolved** | `INSERT/UPDATE assets` (Publish XOR Import) | untouched |

The **manifest is written once** at `create-project` (one per Job) and only rewritten on a breaking schema
change (`manifest_version` bump). It never holds Runs/Versions/Publishes/Deliveries — the
Episode/Sequence/Shot structure is discovered by **walking the deterministic ADR-0003 tree**, and all
provenance is in Postgres. **There is no per-asset manifest:** the handoff between steps is the
**Publish pointer + DB resolve**. Gate counters (`v###` / `p###` / client `v#`) are allocated by the
**writer (Submitter)**, never by a DB trigger; the DB does no orchestration. Crucially,
**`VersionRecorded` fires only after a take's output has landed and its `address` is persisted** — the
Submitter writes the address on render completion (a Flamenco-controller callback, or a synchronous
Runner's return), so the Roustabout always reacts to a real, addressable artifact and never has to poll
or write the pointer itself (ADR 0013). **Notion is a one-way read view**, never the source of truth.

### Spellbook & recipes (where craft lives, how it feeds back)

The **Spellbook** is a `spellbook/` folder in this repo (`spells/`, `templates/`, `templates/blocks/`),
distributed by Git (ADR 0009) — not Notion. A **Template** (verified prompt pattern, built from **Blocks**)
turns a **Brief** into a **Submission Prompt**; its reference is recorded as `runs.template_ref`. A
Template also declares its **knobs** — the param keys a Run's `spec` may sweep (`cfg`,
`lora.character.strength`, `seed`, …) and each knob's mapping to a Comfy node / API slot; the per-`run.type`
**spec** contract (xy-plot axes = knob + explicit values with N=points; seed/prompt/comp/upscale/depth
specs; all inputs via bindings) is **ADR 0016**. The
**recipe** is stored in two parts (ADR 0007): the **authoring** recipe once on the **Run**, and the
**frozen Submission Prompt + resolved params** per **Version** (immutable, self-reproducing — re-authoring
a Template can never invalidate an existing Version). Feedback loop: a method is first written as a
**Spell**; when invoked often enough it **graduates into a Skill** in `skills/`.

---

## Open / to-confirm (kept in sync with HANDOFF.md)

- **Episode token in the Shot code** — **resolved (ADR 0015):** included — `JOB_EP_SEQ_SHOT`
  (`AWA_EP01_SALEM_010`), because Sequence names recur across Episodes. Does not affect this flow's shape.
- **What a Template's "function" keys on** — **resolved:** a Template's function = **workflow-type/mode**
  (`t2v`/`i2v`/`r2v`, = `runs.mode`); a **Block's** function = **prompt-purpose** (camera/style/lighting/
  motion). Spellbook indexes Templates by model×mode, Blocks by model×purpose.
- **Roustabout `FLOWS[run.type]`** — exact deterministic flow per `run.type` (incl. `depth-pass` and the
  Asset Runs: proxy? contact-sheet? auto-publish?) is the next implementation grill (HANDOFF §OPEN 5).
