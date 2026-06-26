---
name: submitter
description: >
  The pipeline's connective tissue. Ingests information about a step, logs it as a Run,
  and passes it to the next step. Writes Run records to the database on Mckenna and to
  the Project's manifest.json, and dispatches heavy render/gen jobs to Flamenco.
  Use whenever a pipeline step starts or finishes, or when the user says "log this run",
  "submit to render", or "hand off to the next step".
---

# submitter

> **Status:** Stub (v0.1). The core architecture lands in Session 5, where the Manifest
> schema and logging format get an ADR. Treat the steps below as the intended shape,
> not final behavior.

## Purpose
One front door for every pipeline step so nothing happens "off the books." Every Skill
that produces or consumes assets routes its bookkeeping through the Submitter:

```
ingest  →  log  →  pass
```

- **Ingest** — receive the step's info: which Project, which Skill, inputs, params.
- **Log** — write a **Run** record to (a) the Project's `manifest.json` and
  (b) the database on **Mckenna**. The manifest is the local truth; Mckenna is the
  queryable, cross-project truth.
- **Pass** — hand off to the next step. For heavy work, this means **dispatching a job
  to Flamenco** on Mckenna and recording the returned `flamenco_job_id` on the Run.

## Inputs
- `project` — the Project this Run belongs to.
- `skill` — the Skill/step being run (e.g. `depth-pass`).
- `inputs` — list of input asset paths/ids.
- `params` — the step's settings.
- `next` *(optional)* — the next step to pass to (and whether it's a Flamenco job).

## Steps
1. Validate the Project exists and load its `manifest.json`.
2. Open a **Run**: assign `run_id`, capture `started`, `inputs`, `params` (status `running`).
3. Persist the open Run to the manifest **and** the Mckenna DB.
4. Let the calling Skill do its work; receive its `outputs`.
5. Close the Run: record `outputs`, `finished`, status `done` (or `failed` + error).
6. If `next` is a render/gen job → submit to **Flamenco**, store `flamenco_job_id`,
   set status `dispatched`, and record the handoff.
7. Update both manifest and Mckenna DB; return the `run_id`.

## Outputs
- A complete **Run** record in `manifest.json` and the Mckenna DB.
- (When dispatched) a Flamenco job id linked to the Run.

## Open questions (resolve in Session 5 → ADR)
- **Runner dispatch surfaces — headless vs agent.** Runners split by surface (see
  `fleet/runners/magnific.py`): REST runners (api-key) the atomic Submitter can call
  **headless**; MCP runners (OAuth, e.g. Magnific `video_generate` → Seedance 2.0) that only an
  **agent** can call (this Claude Code now; **Hermes**/Griptape later). The MCP runner already
  **emits a dispatch spec** (`{tool, slug, params, missing_required}`); decide who *executes* it.
  Recommended shape (deferred 2026-06-25): the **agent/conductor runs the MCP tool** (per ADR-0010 the
  atomic Submitter can't, and shouldn't, orchestrate or hold OAuth), then a **plain-Python finalizer**
  downloads the asset into `<Shot>/versions/<stage>/v###` and writes the Run/Version. Rejected for now:
  a headless OAuth+JSON-RPC MCP client inside the Submitter (biggest build, conflicts with the atomic
  Submitter). See memory `magnific-runner-status`.
- **Griptape**: does it implement the orchestration (ingest/log/pass), or does the
  Submitter stay plain Python and call Flamenco/DB directly? (Decide, then ADR.)
- Manifest ↔ Mckenna DB **sync strategy**: write-through both, or manifest-first with
  a sync job? What's the source of truth on conflict?
- Run **id scheme** and how Flamenco job ids map back to Runs.

## See also
- `schemas/manifest.schema.json` — the Run/Manifest shape this Skill reads/writes.
- `skills/depth-pass/SKILL.md` — first Skill that logs through the Submitter.
