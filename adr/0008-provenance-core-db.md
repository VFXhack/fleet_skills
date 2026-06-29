# ADR 0008 — Provenance core: own thin Postgres on Mckenna (Notion demoted to a view; project index as a table)

**Status:** Accepted
**Date:** 2026-06-24
**Amended by:** ADR 0020 — a Sequence now carries a small **config** record (+ a Sequence Pattern of
prototype Runs) in this DB. The "Episode/Sequence/Shot structure is **never** stored in the DB" stance is
relaxed for Sequence **config only** — a Sequence's *existence* still comes from walking the tree; the DB
holds its *settings*, never the authority on what Sequences exist. Current live truth: `CONTEXT.md`.

## Context
Branch 4. ADR 0006 left `manifest.db_project_id` **null pending this decision**, and "Mckenna's DB"
was de facto the **Notion "Video Generations log."** After ADRs 0005 + 0007, the core is now well
characterised: a `runs → versions → publishes → deliveries` **pointer-graph** plus **asset-binding**
edges, plus a **frozen Submission Prompt (JSON)** per Version — **written by machines from multiple
Fleet boxes**, and **read by lineage traversal** ("walk the pointers"). CONTEXT.md already calls this
"the dynamic, queryable provenance log."

Five options were weighed: **(1)** keep Notion as source of truth; **(2)** build our own DB, Notion as
a view; **(3)** roll a bespoke front-end; **(4)** adopt a VFX platform (Autodesk **Flow** /
**AYON** / **Kitsu**) via API; **(5)** a bare-bones tool-fed DB.

Decisive facts:
- The workload is a **relational pointer-graph + per-row JSON**, queried by **recursive lineage** —
  not a document/relation workload Notion can serve as a *source of truth* (no recursive lineage
  queries, relations buckle at sweep volume, the writer is a rate-limited API). **Option 1 is out
  for the core.**
- The **model is already specified** (0005/0007), so "bare-bones" (5) collapses into (2): a thin
  schema our tools write to. A bespoke UI (3) is premature for a solo operator.
- **Adopting a platform (4)** is a Context-Mapping decision, not a tooling one: it imports a foreign
  ubiquitous language. **AYON**'s model overlaps ours, but its value is **multi-artist / multi-DCC
  studio publishing** (Maya/Houdini/Nuke) — not our solo, API/Comfy, gen-AI-video case — and our
  bespoke **gated-namespace counters**, **lineage-by-pointer**, and **Role-on-binding** would need a
  permanent **anticorruption layer** for little gain at this scale.

## Decision
The **provenance core is a thin relational DB we own, in our own UL, hosted on Mckenna** (already the
designated DB host).

- **Engine: PostgreSQL.** Chosen over SQLite because **multiple Fleet machines write** — the Submitter
  runs from whichever workstation kicks a job (Watts/Leary), plus the future **Hermes** agent on
  Ramdass — and a single-file DB on a network mount is a corruption risk. Postgres is built for
  **many clients, one ledger**. (SQLite would only win under a committed **single write-funnel**, which
  was explicitly declined.)
- **Tables are the UL nouns:** `projects`, `runs`, `versions`, `publishes`, `deliveries`, `assets`,
  `bindings` — plus the **JSONB frozen-submission** column on `versions` (ADR 0007). **Lineage = FK
  pointer edges**, walked with recursive queries. Gate counters (`v###` / `p###` / client `v#`) stay
  per-gate; numbers never leak across gates.
- **`db_project_id` = a `projects` row UUID.** The **project index *is* the `projects` table** — not a
  flat file. The bootstrap ("find the DB before you have a record") is solved like `base_path`:
  **Fleet config carries the Postgres DSN per machine** (the ADR 0002 resolution pattern).
- **Notion is demoted to a one-way read view** (DB → Notion mirror) for human eyeballing; it is
  **never** the source of truth. The existing Notion "Video Generations log" **migrates into Postgres**.
- **Not adopted: Flow / AYON / Kitsu.** AYON's event-driven **Workflows** is recorded as a *reference
  design* for the **Griptape orchestration layer** (Branch 5) — on the conductor side of the wall,
  **not** the ledger.

## Consequences
- **`db_project_id` becomes non-null:** `create-project` must insert a `projects` row and write the
  UUID into the Manifest. *(This is a further reason `create-project` is stale — see HANDOFF heads-up;
  it already needed the ADR-0003 tree + ADR-0005 spine.)*
- **Provenance writes target Postgres; the Manifest still holds none** — ADR 0006 stays intact.
- **Orchestration stays out of the DB:** no triggers doing domain work; `VersionRecorded` is handled by
  Griptape (Branch 5), which renders the proxy and writes the pointer back.
- **Invoices / commercials are explicitly out of scope** for this core — a **separate bounded context**
  (hangs off `Delivery`), to be sited in a later branch. Fine to leave in Notion keyed off Delivery IDs
  until then.
- **New infrastructure:** a Postgres instance on Mckenna; a thin **data-access layer** (repository —
  where the UL meets SQL); a **one-way Notion sync**; a **Notion → Postgres migration** of the existing log.
- Glossary gains a provenance-store term; the **Branch 4** open question closes.

## Why an ADR
"What *is* Mckenna's DB" is the boundary every tool depends on — the Submitter, `create-project`, and
every query — and it sets `db_project_id`. It reverses expensively (re-homing all run/version data) and
it rejects the two tempting defaults (keep Notion as truth; adopt a studio platform), so the reasoning
must be on record.
