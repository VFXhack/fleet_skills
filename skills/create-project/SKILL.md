---
name: create-project
description: >
  Scaffold and register a new production Project: stamp the canonical ADR-0003
  folder tree on the Huxley store, insert a row in the Postgres provenance core,
  and write the thin manifest with the returned db_project_id. Use when starting a
  new Job/Project, or when the user says "new project", "set up a project", or
  "scaffold a project". Ensures no project is ever ad-hoc.
---

# create-project

> **Status:** v1.0 — backed by the `fleet` Python package (`fleet.cli`). Implements
> ADR 0003 (structure), ADR 0006 (thin manifest), ADR 0008 (provenance DB).

## When to use
Starting any new **Job** (= Project). Run this *before* generating any assets so
everything lands in the canonical place and the provenance core knows the project exists.

## Inputs
- `--client` — `client_code`, e.g. `WBTV` (matches `[A-Za-z0-9_-]+`).
- `--job` — `job_code` (= the Project), e.g. `AWA`.
- `--title` — human-readable title, e.g. `"Are We Alone"`.
- `--episode` — first episode code (default `EP01`; ADR-0003 keeps an Episode always present).
- `--dry-run` — print the plan and touch nothing.

## How it runs
From the repo root, with the project venv:
```
.\.venv\Scripts\python.exe -m fleet.cli --client WBTV --job AWA --title "Are We Alone"
```
(or the installed entrypoint `create-project --client WBTV --job AWA --title "Are We Alone"`).

It resolves the DB DSN and the real projects root from `~/.fleet/config.toml`
(`FLEET_DB_DSN` / `FLEET_PROJECTS_ROOT` override). base_path resolves to the Huxley
`io_common` share on Watts (ADR 0002).

## What it does (in order, fail-safe)
1. Validate codes; compute `job_dir = <projects_root>/<client>/<job>` and the logical
   `base_path = fleet:/projects/<client>/<job>/`.
2. Refuse if the dir exists non-empty or the project is already registered in the DB.
3. `INSERT` a `projects` row → get the `db_project_id` (UUID).
4. Scaffold the ADR-0003 job skeleton (`_ops/{scripts,logs,config,jobs}`, `assets/`,
   `editorial/`, `<EPISODE>/deliverables/`), write `manifest.json` (thin, ADR 0006) and a
   starter project `CONTEXT.md`.
5. Commit. On any failure after step 3, the DB row is rolled back and a freshly-created
   job dir is removed.

## Outputs
- A canonical Project folder on the Huxley store.
- A `projects` row in the provenance core; its UUID written into the manifest's `db_project_id`.

## Notes
- Episodes/Sequences/Shots below the first Episode are added on demand by later tools,
  not here.
- The shared `fleet` package (config / db / repository / manifest / scaffold) is the
  same DB-access layer the Submitter and runners will reuse.
