-- ============================================================================
-- 0002_run_spec.sql — add runs.spec (per-run-type operation/variation; ADR 0016)
-- ============================================================================
-- The authoring recipe (ADR 0007) is: type + bindings + params + spec.
--   * params = the FIXED base knobs held constant across the run.
--   * spec   = the TYPE-SPECIFIC variation/operation definition (xy-plot axes,
--              seed list, prompt variants, comp .nk ref, upscale/depth params).
-- Kept separate from params so the baseline and the variation are not conflated.
--
-- The Submitter VALIDATES spec's knob names against the Template's declared knobs
-- (the DB does no domain work; ADR 0008), then EXPANDS spec into N versions, each
-- carrying its resolved versions.delta + frozen_submission. Sweep values are
-- stored EXPLICIT (range+steps is submit-time sugar; steps count DATA POINTS).
-- All inputs (incl. the Source an upscale/comp/depth/refine consumes) are
-- BINDINGS by role, so this column carries no input pointers (ADR 0016).
-- ============================================================================

BEGIN;

ALTER TABLE runs
    ADD COLUMN spec jsonb NOT NULL DEFAULT '{}'::jsonb;  -- per-type op/variation (ADR 0016)

COMMIT;
