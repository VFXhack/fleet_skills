-- ============================================================================
-- 0001_initial_schema.sql — Fleet provenance core (ADR 0008)
-- ============================================================================
-- Engine: PostgreSQL 13+ (uses built-in gen_random_uuid()).
-- Host:   Mckenna (the Fleet DB host).
-- Scope:  The system of record for ALL provenance. Seven UL-named tables form a
--         runs -> versions -> publishes -> deliveries pointer-graph, plus
--         asset-binding edges. Lineage = FK pointer edges, walked with recursive
--         queries. Gate counters (v### / p### / client v#) are per-gate and
--         never leak across gates (ADR 0005). The frozen Submission Prompt is a
--         JSONB value object on `versions` (ADR 0007).
--
-- NON-OBVIOUS DECISIONS baked into this schema (each tied to an ADR):
--   * Shot is a TEXT CODE, not a table/FK. The Episode/Sequence/Shot structure is
--     discovered by walking the deterministic tree, NOT stored in the DB
--     (ADR 0003, ADR 0006). Artifacts carry `shot_code` (e.g. 'AWA_SALEM_010').
--   * `shot_code` is DENORMALIZED onto versions/publishes/deliveries so each
--     gate's per-shot counter can be enforced with a plain UNIQUE constraint and
--     lineage queries stay cheap. (A Run already binds a shot; we copy it down.)
--   * Gate counters are stored as integers + UNIQUE(shot_code, n); the next value
--     is allocated by the writer (the Submitter), NOT by a DB trigger — the DB
--     does no domain/orchestration work (ADR 0008).
--   * Authoring-level recipe (template ref, model/tier/mode, flat params, and the
--     asset->role BINDINGS) lives ONCE on the Run; the resolved-level frozen
--     submission lives per Version (ADR 0007). Hence `bindings.run_id`.
-- ============================================================================

BEGIN;

-- gen_random_uuid() is in core since PG 13. (pgcrypto fallback if ever on <13.)
-- CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ----------------------------------------------------------------------------
-- projects — the project index IS this table (ADR 0008). manifest.db_project_id
-- points at projects.id. One row per Job (= Project; ADR 0003 "Project = Job").
-- ----------------------------------------------------------------------------
CREATE TABLE projects (
    id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    client_code  text        NOT NULL,                 -- e.g. 'WBTV'
    job_code     text        NOT NULL,                 -- e.g. 'AWA' (= Project id)
    title        text        NOT NULL,                 -- e.g. 'Are We Alone'
    status       text        NOT NULL DEFAULT 'active'
                 CHECK (status IN ('active','idle','delivered','archived')),
    base_path    text        NOT NULL,                 -- logical, platform-neutral: fleet:/projects/<client>/<job>/
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (client_code, job_code)
);

-- ----------------------------------------------------------------------------
-- runs — one Submit event against a Shot (ADR 0005). Holds the AUTHORING-level
-- recipe shared across the take(s) it produces (ADR 0007). Produces 1..N versions.
-- Also logs non-gen-AI Skill runs (e.g. a depth-pass Run -> a depth Publish).
-- ----------------------------------------------------------------------------
CREATE TABLE runs (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id    uuid        NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    shot_code     text        NOT NULL,                -- 'AWA_SALEM_010' (walked, not an FK)
    type          text        NOT NULL,                -- 'seed-sweep' | 'prompt-variation' | 'xy-plot' | 'refine' | ...
    -- authoring-level recipe (shared; ADR 0007):
    template_ref  text,                                -- Spellbook Template reference (may be null for non-gen Skill runs)
    model         text,                                -- model id / family
    tier          text,                                -- quality/speed tier
    mode          text,                                -- workflow mode (t2v/i2v/r2v/...)
    params        jsonb       NOT NULL DEFAULT '{}'::jsonb,  -- flat params common to the run
    request_id    text,                                -- upstream request/job id
    cost          numeric(12,4),                       -- run cost if known
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX runs_project_idx ON runs (project_id);
CREATE INDEX runs_shot_idx    ON runs (shot_code);

-- ----------------------------------------------------------------------------
-- versions — one take/output a Run produces (ADR 0005). Numbered per Shot (v###).
-- Carries the RESOLVED-level recipe: an immutable frozen Submission Prompt +
-- resolved params (JSONB value object, ADR 0007) sufficient on its own to
-- reproduce the take. Its `address` (model output URL) is EPHEMERAL — nothing
-- downstream may point at a Version.
-- ----------------------------------------------------------------------------
CREATE TABLE versions (
    id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id             uuid        NOT NULL REFERENCES runs(id) ON DELETE RESTRICT,
    shot_code          text        NOT NULL,           -- denormalized from run for the per-shot counter
    number             integer     NOT NULL,           -- per-Shot work counter -> v###
    stage              text        NOT NULL DEFAULT 'render'
                       CHECK (stage IN ('render','upscale','comp')),   -- ADR 0003 versions/<stage>/
    delta              jsonb       NOT NULL DEFAULT '{}'::jsonb,        -- the swept value (e.g. {"seed": 777})
    frozen_submission  jsonb       NOT NULL,           -- exact payload sent; immutable (ADR 0007)
    address            text,                           -- ephemeral model output URL/path (may rot)
    created_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (shot_code, number)
);
CREATE INDEX versions_run_idx ON versions (run_id);

-- ----------------------------------------------------------------------------
-- publishes — a Version promoted past the INTERNAL gate (ADR 0005). THIN:
-- identity + pointer back to its source Version (recipe never duplicated).
-- Own per-Shot counter (p###); does NOT inherit the Version number. The only
-- thing downstream contexts may reference.
-- ----------------------------------------------------------------------------
CREATE TABLE publishes (
    id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    source_version_id  uuid        NOT NULL REFERENCES versions(id) ON DELETE RESTRICT,  -- lineage pointer
    shot_code          text        NOT NULL,
    number             integer     NOT NULL,           -- per-Shot publish counter -> p###
    path               text,                           -- stable, downstream-safe address in <Shot>/publishes/
    created_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (shot_code, number)
);
CREATE INDEX publishes_source_idx ON publishes (source_version_id);

-- ----------------------------------------------------------------------------
-- deliveries — a Publish promoted across the CLIENT gate (ADR 0005). A special
-- kind of Publish: points back to its source Publish. Client-facing counter that
-- RESETS at the gate (client v1, v2, ...) so the client's first sight is v1
-- regardless of internal churn.
-- ----------------------------------------------------------------------------
CREATE TABLE deliveries (
    id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    source_publish_id  uuid        NOT NULL REFERENCES publishes(id) ON DELETE RESTRICT,  -- lineage pointer
    shot_code          text        NOT NULL,
    client_number      integer     NOT NULL,           -- client-facing counter -> v#
    delivered_at       timestamptz NOT NULL DEFAULT now(),
    UNIQUE (shot_code, client_number)
);
CREATE INDEX deliveries_source_idx ON deliveries (source_publish_id);

-- ----------------------------------------------------------------------------
-- assets — a versioned INPUT used to make the gen-AI video (ADR 0005). Lives in
-- one of two scopes (Job-shared or Shot-specific; ADR 0003 two-tier). Its content
-- is EITHER a Publish (internal output re-entering) OR an Import (external file) —
-- the Publish-vs-Import distinction (internal HAS a source Version; Import does
-- not) keeps provenance honest. We RESOLVE its current content when wiring.
--
-- UL note: "resolved" (the asset's currently-selected content) is deliberately
-- distinct from the gate verb "promote" (Version->Publish->Delivery). An asset's
-- resolved content may be a Publish (which DID cross a gate) or an Import (which
-- never does), so the neutral "resolved" covers both; "promote" stays the gate
-- verb only. (Also avoids the promote/prompt look-alike.)
--
-- NOTE: Import has no table of its own among the seven. An Import is represented
-- inline on the asset row (import_uri + metadata); an internal Asset points at a
-- Publish. Exactly one is set.
-- ----------------------------------------------------------------------------
CREATE TABLE assets (
    id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id            uuid        NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    scope                 text        NOT NULL CHECK (scope IN ('job','shot')),
    shot_code             text,                         -- required iff scope='shot'
    name                  text        NOT NULL,         -- descriptive, e.g. 'main character sheet'
    -- resolved content: an internal Publish XOR an external Import
    resolved_publish_id   uuid        REFERENCES publishes(id) ON DELETE RESTRICT,
    import_uri            text,                          -- external file location (client plate, stock, scan)
    import_meta           jsonb,                         -- checksum, source, etc. (external provenance)
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now(),
    CHECK (scope = 'shot' AND shot_code IS NOT NULL
           OR scope = 'job' AND shot_code IS NULL),
    -- exactly one content source (or none yet, while being set up):
    CHECK (NOT (resolved_publish_id IS NOT NULL AND import_uri IS NOT NULL))
);
CREATE INDEX assets_project_idx ON assets (project_id);

-- ----------------------------------------------------------------------------
-- bindings — the {asset -> pinned Publish/Import, role} edge (ADR 0005). Role
-- lives on the BINDING (Asset x usage), not on the Asset. Authoring-level, so it
-- hangs off the RUN (shared across a sweep; ADR 0007). Role is the wiring key:
-- how to reference the Asset in the prompt AND which Comfy node / API slot to
-- feed it into.
-- ----------------------------------------------------------------------------
CREATE TABLE bindings (
    id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id             uuid        NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    asset_id           uuid        NOT NULL REFERENCES assets(id) ON DELETE RESTRICT,
    pinned_publish_id  uuid        REFERENCES publishes(id) ON DELETE RESTRICT,  -- pinned content (internal)
    pinned_import_uri  text,                             -- pinned content (external), mirrors assets.import_uri
    role               text        NOT NULL,             -- 'First-Frame' | 'Last-Frame' | 'Depth-Pass' | 'Style' | ...
    created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX bindings_run_idx   ON bindings (run_id);
CREATE INDEX bindings_asset_idx ON bindings (asset_id);

COMMIT;
