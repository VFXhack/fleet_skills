# ADR 0003 — Canonical Project structure: shot-centric, two-tier assets

**Status:** Accepted
**Date:** 2026-06-24
**Amended by:** ADR 0015 — the Shot code includes the Episode token (`JOB_EP_SEQ_SHOT`,
`AWA_EP01_SALEM_010`); the `JOB_SEQUENCE_SHOT` / `AWA_SALEM_010` / `<JOB_SEQ_SHOT>` examples below predate
that resolution.

## Context
The legacy layout (see `WBTV/AWA`) organized a Project **by task**: the Job root split into
`AI_Frames/`, `AI_Renders/`, `plates/`, `comps/`, `renders/`, etc., and *each* held per-shot
subfolders. One Shot's files were scattered across six top-level folders, version/variant state
was encoded into hundreds of sibling folder names (`_v230_slp-2_5`, `TOPAZ/…`), and pipeline
cruft (PS1, logs, prompts, autosaves, fonts, 3D downloads) accumulated in dumping grounds
(`reference/`, loose `logs/`). Andy flagged it as un-DDD: "too many unspecified folders... there
need to be designed and agreed-upon places for everything."

Production also nests deeper than the first proposal (`client/job/shot`) implied: shot codes are
`JOB_SEQUENCE_SHOT` (`AWA_SALEM_010`), revealing a **Sequence** level, and work is **episodic**.

## Decision
A Project (= a Job) uses one canonical tree. Organization is **shot-centric** (everything for a
Shot lives in that Shot's folder), assets are **two-tier** (Job-shared + Shot-specific only),
and operational files get one home.

```
<client_code>/<job_code>/              Job = Project root  (= base_path; see ADR 0002)
├── manifest.json                      the Project's map (Git ↔ store ↔ renders)
├── CONTEXT.md                         Project-local notes/glossary
├── _ops/                              operational, non-creative
│   ├── scripts/                       PS1 / automation
│   ├── logs/                          local run & job logs
│   ├── config/                        tool config
│   └── jobs/                          Flamenco submission files
├── assets/                            Job-shared assets — FLAT, descriptively named
│                                      (e.g. "main character sheet", "desert environment")
├── editorial/                         Premiere/AE cut assembly (job-wide finishing)
└── <EPISODE>/                         e.g. EP01  (always present; one-offs get EP01)
    ├── deliverables/                  per-Episode final handoff to the Client
    └── <SEQUENCE>/                    e.g. SALEM
        └── <JOB_SEQ_SHOT>/            e.g. AWA_SALEM_010  (folder = full shot code)
            ├── assets/                shot-specific input files (flat, descriptive; role = metadata)
            ├── work/
            │   ├── blender/           .blend + autosave  (the .blend Flamenco renders)
            │   └── nuke/              .nk scripts
            ├── versions/              ALL takes from Runs — ephemeral, recipe attached (v###)
            │   ├── render/            model takes + seed sweeps
            │   ├── upscale/           Topaz tries
            │   └── comp/              comp renders
            └── publishes/             internal-promoted (p###) — stable, canonical, + pointer back
```

Specifics:
- **Hierarchy:** Client → Job → Episode → Sequence → Shot. **Project = the Job.** Episode is
  always a level. (ADR/glossary: *Project anatomy*.)
- **Assets** are two homes only — `<Job>/assets/` (shared across Shots) and `<Shot>/assets/`
  (shot-specific) — stored **flat** and **named for what they are**, not bucketed by type. No
  Episode/Sequence asset level (assets routinely span Episodes).
- **DCC scenes** live per-Shot in `work/`; job-wide finishing lives in Job `editorial/`.
- **Deliverables** are **per-Episode**.
- **Shot outputs split into `versions/` and `publishes/`** (see ADR 0005). Takes and seed sweeps are
  Versions (`v###`, recipe attached); only promoted takes become Publishes (`p###`, stable + pointer
  back). Downstream points only at Publishes; a Publish promoted across the client gate is a Delivery.
- **Prompts** are not loose files — the prompt is part of the **Version's recipe** (with the Version,
  and/or in the Run log on Mckenna), so it is never orphaned.
- **Numbering** lives *inside* `versions/<stage>/` (e.g. `v001/…`); each gate has its own counter
  (Version `v###` → Publish `p###` → Delivery client `v#`), never encoded into top-level folder names.

## Consequences
- To see everything for a Shot you open one folder; the "hunt across six folders" problem is gone.
- `create-project` (and a future scaffolder) can stamp this tree deterministically; the Manifest
  (ADR, branch 2) maps to these well-known paths instead of ad-hoc ones.
- Flamenco must be configured to write each render into that Shot's `renders/` (output path
  templated per Shot) rather than a flat farm dump.
- Legacy Projects (e.g. `AWA`) need a one-time migration into this shape — tracked separately.

## Why an ADR
The on-disk shape is load-bearing for every Skill, the Submitter, and the Manifest; reversing it
means re-homing and re-pathing all Projects. It also deliberately rejects the task-centric layout a
reader would otherwise assume from the legacy tree. That's the bar.
