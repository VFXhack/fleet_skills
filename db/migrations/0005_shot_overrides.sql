-- ============================================================================
-- 0005_shot_overrides.sql — the Override store + the Cast breadcrumb
-- (ADR 0023, settling the ADR 0020 §8 / Open "where do a Shot's Overrides live")
-- ============================================================================
-- An Override is a Shot's local value for an inherited attribute AND a shield
-- against later Sequence-wide changes (ADR 0020 §8). Cast reads this store to
-- apply it; Hoist reads it to leave shielded siblings alone, and deletes the
-- look-dev Shot's rows for attributes it just hoisted (now redundant).
--
-- NON-OBVIOUS DECISIONS (ADR 0023):
--   * Keyed by STABLE CODES (shot_code text, run_type), never look_run_id —
--     Hoist is rebuild-fresh (ADR 0022): Look Runs get new uuids every Hoist,
--     so an FK to them would be orphaned by the very Hoist it shields against.
--   * One row per overridden attribute, in exactly TWO forms (CHECK-enforced):
--       param override    param_key + param_value   e.g. cfg -> 4.0
--       binding override  role + asset_id           e.g. Character-Sheet -> own sheet
--   * Uniqueness needs two PARTIAL indexes (half the key is NULL on each form);
--     a plain UNIQUE over nullable columns would never collide.
--   * Shots stay codes, not rows — this is attribute config, not structure
--     (same carve-out as sequences, ADR 0020 §2).
-- ============================================================================

BEGIN;

CREATE TABLE shot_overrides (
    id           uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    sequence_id  uuid        NOT NULL REFERENCES sequences(id) ON DELETE CASCADE,
    shot_code    text        NOT NULL,   -- e.g. 'AWA_EP01_SALEM_020' (walked, not an FK)
    run_type     text        NOT NULL,   -- the targeted Look Run's stable identity (ADR 0014 enum)
    -- param override:
    param_key    text,
    param_value  jsonb,
    -- binding override:
    role         text,
    asset_id     uuid        REFERENCES assets(id) ON DELETE RESTRICT,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    -- exactly one of the two forms:
    CHECK (
           (param_key IS NOT NULL AND param_value IS NOT NULL AND role IS NULL AND asset_id IS NULL)
        OR (param_key IS NULL     AND param_value IS NULL     AND role IS NOT NULL AND asset_id IS NOT NULL)
    )
);

-- one override per attribute (partial: each form keys on its own column)
CREATE UNIQUE INDEX shot_overrides_param_uq
    ON shot_overrides (sequence_id, shot_code, run_type, param_key)
    WHERE param_key IS NOT NULL;
CREATE UNIQUE INDEX shot_overrides_role_uq
    ON shot_overrides (sequence_id, shot_code, run_type, role)
    WHERE role IS NOT NULL;

CREATE INDEX shot_overrides_shot_idx ON shot_overrides (sequence_id, shot_code);

-- ----------------------------------------------------------------------------
-- runs.cast_from — the Cast provenance breadcrumb (ADR 0020 §7: "record the
-- look_version it was built from"). NULL unless the Run was Cast from a Sequence
-- Look; then {"sequence_code": ..., "look_version": N, "ord": i} — codes, not
-- Look-Run uuids, for the same rebuild-fresh reason as above.
-- ----------------------------------------------------------------------------
ALTER TABLE runs ADD COLUMN cast_from jsonb;

COMMIT;
