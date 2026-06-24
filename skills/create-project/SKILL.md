---
name: create-project
description: >
  Scaffold a new production Project with the standard folder structure, starter
  CONTEXT.md, README, and manifest.json. Use whenever starting a new shot, sequence,
  or deliverable, or when the user says "new project", "set up a project", or
  "scaffold a project". Ensures no project is ever ad-hoc.
---

# create-project

> **Status:** Draft template (v0.1). Refine inputs/steps during Session 2.

## When to use
Starting any new bounded piece of production work. Run this *before* generating any
assets so everything lands in the right place and the Submitter can track it.

## Inputs
- `project_name` — short, filesystem-safe (e.g. `acme-teaser-01`).
- `description` — one line: what this project is.
- `base_path` — where projects live on the Fleet drive (default: `<FILL IN>`).

## What it creates
```
<base_path>/<project_name>/
├── CONTEXT.md          # project-specific ubiquitous language + decisions
├── README.md           # one paragraph: what / why / status
├── manifest.json       # inputs, models, params, output locations (Submitter reads/writes)
├── 00_input/           # source plates, footage, reference stills (read-only originals)
├── 01_depth/           # depth passes  ← output of the depth-pass skill
├── 02_gen/             # gen-AI outputs, versioned (v001, v002, …)  [dispatched via Flamenco]
├── 03_comp/            # composites / edits
├── 04_output/          # final approved deliverables
├── scripts/            # project-specific scripts
├── config/             # fal configs, model param sets, prompt files
├── logs/               # Submitter logs: ingest → log → handoff records
└── adr/                # decisions specific to this project
```

## Steps
1. Validate `project_name` is filesystem-safe and not already taken under `base_path`.
2. Create the folder tree above.
3. Write a starter `CONTEXT.md` (inherits the system glossary; add project-specific terms).
4. Write `README.md` from `description`, with status = `idle`.
5. Write an empty `manifest.json` (schema TBD — see ADR from Session 5):
   ```json
   { "project": "<project_name>", "created": "<iso8601>", "inputs": [], "runs": [], "outputs": [] }
   ```
6. Write `.gitignore` ignoring the heavy folders: `00_input/ 01_depth/ 02_gen/ 03_comp/ 04_output/`.
7. Register the project in the project index (location TBD).
8. Print the created path and next suggested step (usually: drop plates in `00_input/`).

## Outputs
- A ready-to-use Project folder on the Fleet drive.
- A registered entry so the Submitter knows the project exists.

## Open questions (resolve in Session 2)
- Final `base_path` for projects on Fleet.
- Manifest schema (coordinate with the Submitter ADR, Session 5).
- Where the project index lives (flat file vs DB on Mckenna).
