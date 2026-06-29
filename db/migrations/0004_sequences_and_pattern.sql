-- ============================================================================
-- 0004_sequences_and_pattern.sql — Sequence shared state + Sequence Pattern
-- (ADR 0020; amends ADR 0003 two-tier assets, ADR 0008/0011 "no structure in DB")
-- ============================================================================
-- A Sequence stops being a bare folder token and gains a CONFIG record + a
-- Sequence Pattern (a set of prototype Runs every Shot is built to). Existence
-- still comes from the deterministic tree (ADR 0003) — the DB stores a Sequence's
-- SETTINGS, never the authority on which Sequences exist.
--
-- Three sharing classes drive what propagates (ADR 0020 §1):
--   * shared-content  one artifact, every Shot uses it  -> assets.scope='sequence'
--   * shared-recipe   same settings, content regenerated per Shot -> a prototype Run
--   * per-shot        different per Shot, no sharing     -> assets.scope='shot'
--
-- NON-OBVIOUS DECISIONS (each tied to ADR 0020):
--   * sequences is CONFIG, not structure. No FK from runs/versions to it; Shots
--     still carry shot_code text and are walked, not joined.
--   * The Pattern mirrors the runs/bindings shapes on purpose: Hoist = copy a
--     recipe UP, Instantiate = clone it DOWN (same op, two directions).
--   * A Sequence Asset's FILE still lives flat in <Job>/assets/; scope='sequence'
--     is a BINDING scope, not a new folder (ADR 0003 "scope/Role is metadata").
-- ============================================================================

BEGIN;

-- ----------------------------------------------------------------------------
-- sequences — per-Sequence CONFIG (ADR 0020 §2). One row per Sequence folder.
-- ----------------------------------------------------------------------------
CREATE TABLE sequences (
    id                 uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id         uuid        NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
    sequence_code      text        NOT NULL,            -- e.g. 'AWA_EP01_SALEM' (ADR 0015 form)
    title              text,
    lookdev_shot_code  text,                            -- the designated Target Shot (ADR 0020 §5); nullable
    pattern_version    integer     NOT NULL DEFAULT 0,  -- bumped by each Hoist (ADR 0020 §7)
    created_at         timestamptz NOT NULL DEFAULT now(),
    updated_at         timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, sequence_code)
);
CREATE INDEX sequences_project_idx ON sequences (project_id);

-- ----------------------------------------------------------------------------
-- sequence_pattern_runs — the prototype Runs of a Sequence Pattern (ADR 0020 §3).
-- Mirrors the runs authoring recipe MINUS per-Shot content (no shot_code, no
-- versions). A Shot instantiates each into a real runs row.
-- ----------------------------------------------------------------------------
CREATE TABLE sequence_pattern_runs (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    sequence_id   uuid        NOT NULL REFERENCES sequences(id) ON DELETE CASCADE,
    type          text        NOT NULL,                -- ADR 0014 enum (render/control-pass/upscale/...)
    stage         text        NOT NULL DEFAULT 'render'
                  CHECK (stage IN ('render','upscale','comp')),
    template_ref  text,
    model         text,
    tier          text,
    mode          text,
    params        jsonb       NOT NULL DEFAULT '{}'::jsonb,  -- shared authoring params (LUT, CFG, workflow)
    ord           integer     NOT NULL DEFAULT 0,            -- order in the per-Shot chain
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX sequence_pattern_runs_seq_idx ON sequence_pattern_runs (sequence_id);

-- ----------------------------------------------------------------------------
-- sequence_pattern_bindings — per-Role inputs of a prototype Run, tagged with the
-- sharing class (ADR 0020 §3; class is assigned at Hoist, ADR 0020 §6). A binding
-- is sourced EXACTLY ONE of three ways, by class:
--   * shared-content -> asset_id  (a Sequence-scoped Asset; one file, every Shot)
--   * shared-recipe  -> produced_by_pattern_run_id  (another prototype Run whose
--       output feeds this Role, RE-RUN per Shot; its per-Shot take is auto-published
--       no-look by the Roustabout, ADR 0018, then bound in — no new machinery)
--   * per-shot       -> neither   (the Shot supplies its own input)
-- ----------------------------------------------------------------------------
CREATE TABLE sequence_pattern_bindings (
    id                          uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_run_id              uuid        NOT NULL REFERENCES sequence_pattern_runs(id) ON DELETE CASCADE,
    role                        text        NOT NULL,   -- 'Character-Sheet' | 'Depth-Pass' | 'Lipsync-Dialog' | ...
    sharing_class               text        NOT NULL
                                CHECK (sharing_class IN ('shared-content','shared-recipe','per-shot')),
    asset_id                    uuid        REFERENCES assets(id) ON DELETE RESTRICT,               -- shared-content source
    produced_by_pattern_run_id  uuid        REFERENCES sequence_pattern_runs(id) ON DELETE CASCADE, -- shared-recipe source
    created_at                  timestamptz NOT NULL DEFAULT now(),
    -- source must match class (exactly one of asset / producer / neither):
    CHECK (
           (sharing_class = 'shared-content' AND asset_id IS NOT NULL AND produced_by_pattern_run_id IS NULL)
        OR (sharing_class = 'shared-recipe'  AND asset_id IS NULL     AND produced_by_pattern_run_id IS NOT NULL)
        OR (sharing_class = 'per-shot'       AND asset_id IS NULL     AND produced_by_pattern_run_id IS NULL)
    )
);
CREATE INDEX sequence_pattern_bindings_run_idx ON sequence_pattern_bindings (pattern_run_id);

-- ----------------------------------------------------------------------------
-- assets — add the Sequence binding scope (ADR 0020 §4). Three scopes now; the
-- file still lives flat in <Job>/assets/. scope='sequence' requires sequence_code.
-- ----------------------------------------------------------------------------
ALTER TABLE assets ADD COLUMN sequence_code text;                 -- required iff scope='sequence'

ALTER TABLE assets DROP CONSTRAINT assets_scope_check;            -- was: scope IN ('job','shot')
ALTER TABLE assets ADD  CONSTRAINT assets_scope_check
    CHECK (scope IN ('job','sequence','shot'));

ALTER TABLE assets DROP CONSTRAINT assets_check;                  -- was: shot_code presence by scope (job/shot only)
ALTER TABLE assets ADD  CONSTRAINT assets_scope_code_check CHECK (
       (scope = 'job'      AND shot_code IS NULL     AND sequence_code IS NULL)
    OR (scope = 'sequence' AND shot_code IS NULL     AND sequence_code IS NOT NULL)
    OR (scope = 'shot'     AND shot_code IS NOT NULL)
);

COMMIT;
