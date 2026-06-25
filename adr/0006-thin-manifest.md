# ADR 0006 — Thin Manifest (map header), provenance in the DB

**Status:** Accepted
**Date:** 2026-06-24

## Context
The seed `manifest.schema.json` was **fat**: it embedded `inputs[]`, `runs[]`, and `outputs[]`
arrays inline, used an absolute `base_path`, a flat `project` name, a `00_input/01_depth` folder
convention, and a single `version` + `approved` flag per output. After the artifact model (ADR 0005)
and structure (ADR 0003) were settled, every one of those assumptions is wrong: provenance is now a
`runs → versions → publishes → deliveries` spine with lineage edges, the tree is deterministic and
shot-centric, and `base_path` must be platform-neutral (ADR 0002).

A fat manifest would duplicate two things that already own this data — the **filesystem** (the
deterministic structure) and **Mckenna's DB** (the dynamic, queryable provenance log, which already
exists as the Notion "Video Generations log") — and would drift the moment either changes.

## Decision
`manifest.json` is a **thin per-Project map header** living at the Job root. It contains only:
- **Identity** — `client_code`, `job_code`, `title`, `status`, `created`/`updated`.
- **`base_path`** — the **logical**, platform-neutral root (`fleet:/projects/<client>/<job>/`);
  each machine resolves it to a real path via **Fleet-level config**, not stored per project.
- **Pointers** — `db_project_id` (into Mckenna's DB, where all provenance lives) and optional `links`.
- **`manifest_version`** — an **integer**, bumped by 1 on any breaking schema change; `create-project`
  writes the current version and a migration map upgrades older manifests.

It holds **no** provenance and **no** structural enumeration: Runs/Versions/Publishes/Deliveries
(recipes + lineage) live in the **DB**; Episode/Sequence/Shot/Asset structure is discovered by
**walking the tree**. Kept deliberately minimal — fields are added later as concrete needs appear
(the version bump makes that cheap). Schema: `schemas/manifest.schema.json`.

## Consequences
- The Submitter reads the Manifest only to **locate and identify** a Project and find its DB record;
  it writes provenance to the **DB**, not the Manifest.
- The Manifest can't drift out of sync with reality, because it asserts almost nothing reality owns.
- `db_project_id` is null until the project-index/DB decision lands (next branch) and a record exists.

## Why an ADR
"Where does provenance live" is a boundary decision the Submitter, create-project, and every query
depend on. It reverses expensively (re-homing run/version data) and is surprising to a VFX reader who
expects a fat manifest carrying the shot/version list — exactly the assumption it rejects.
