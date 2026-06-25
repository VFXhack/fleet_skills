# ADR 0011 — Provenance core: physical schema design

**Status:** Accepted
**Date:** 2026-06-25

## Context
ADR 0008 decided *what* the provenance core is (own thin Postgres on Mckenna, 7 UL tables) and
ADRs 0005/0007 fixed the *model* (gated namespaces, lineage-by-pointer, frozen submission per Version).
Turning that into runnable DDL (`db/migrations/0001_initial_schema.sql`) forced several physical
decisions that the prose ADRs left open. They are load-bearing for every tool that touches the DB, so
they are recorded here.

## Decision
The schema is seven tables (`projects`, `runs`, `versions`, `publishes`, `deliveries`, `assets`,
`bindings`). The non-obvious shaping choices:

- **Shot is a text code, not a table.** The Episode/Sequence/Shot structure is discovered by walking
  the deterministic tree (ADR 0003/0006), so there is no `shots` table. Artifacts carry a `shot_code`
  text column (e.g. `AWA_SALEM_010`). A Run references its project by FK but its shot by code.
- **`shot_code` is denormalized onto `versions`/`publishes`/`deliveries`.** Each gate's per-Shot
  counter is then a plain `UNIQUE (shot_code, number)`, and lineage/listing queries stay cheap without
  a join back through `runs`.
- **Gate counters are integers allocated by the writer, never by the DB.** `versions.number` (v###),
  `publishes.number` (p###), `deliveries.client_number` (client v#) are plain ints guarded by the
  unique constraint; the Submitter allocates the next value. No sequences-per-shot, no triggers — the
  DB does no domain work (ADR 0008).
- **Lineage = FK pointer edges:** `publishes.source_version_id → versions`,
  `deliveries.source_publish_id → publishes`, `versions.run_id → runs`, `runs.project_id → projects`,
  walked with recursive queries. `ON DELETE RESTRICT` everywhere so provenance can't be silently cut.
- **Frozen submission is `jsonb` on `versions`** (`frozen_submission`, NOT NULL) — the immutable,
  self-sufficient reproduction payload (ADR 0007). Authoring-level recipe lives once on `runs`
  (`template_ref`, `model`/`tier`/`mode`, `params jsonb`).
- **Bindings hang off the Run** (`bindings.run_id`), because the `{asset → pinned content, role}`
  authoring recipe is shared across a sweep (ADR 0007). `ON DELETE CASCADE` from the run.
- **Asset content is inline; Import has no table.** `assets` carries `resolved_publish_id` (internal,
  FK) **XOR** `import_uri` + `import_meta jsonb` (external), enforced by a CHECK. An Asset's "versions"
  are the Publish lineage chain — re-promoting re-points the asset; no separate `asset_versions` table.
- **UL term `resolved`** names an Asset's currently-selected content, kept distinct from the gate verb
  `promote` (and avoids the `promote`/`prompt` look-alike). Column: `assets.resolved_publish_id`.
- **UUID PKs** via `gen_random_uuid()` (core in PG 13+). All timestamps `timestamptz`.

## Consequences
- The whole migration applies in one transaction; re-keying any of these shapes is an expensive
  reversal (re-homing rows), which is why they are pinned here.
- Tools never look up a shot by FK — they filter by `shot_code`. A future `shots`/structure cache, if
  ever needed, is additive and does not change these tables.
- `create-project` writes only `projects`; the Submitter will write `runs`/`versions` (+ `bindings`),
  and the promote/deliver acts write `publishes`/`deliveries`.

## Why an ADR
The physical schema is the contract every Fleet tool depends on, and these choices (shot-as-code,
denormalized counters, writer-allocated numbers, inline Import, bindings-on-run) are not what a reader
of 0005/0008 would necessarily assume. They reverse expensively, so the reasoning is on record.
