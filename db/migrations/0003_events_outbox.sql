-- ============================================================================
-- 0003_events_outbox.sql — orchestration event outbox (ADR 0019)
-- ============================================================================
-- The DURABLE transport for orchestration events between the Submitter (the sole
-- writer/emitter) and the Roustabout (the deterministic worker). Transactional
-- outbox pattern: the Submitter INSERTs an event row in the SAME transaction as
-- the version/publish write it describes, then issues NOTIFY as a low-latency
-- wakeup. The ROW is the source of truth; the NOTIFY is only a hint that may be
-- missed (ADR 0019). The Roustabout drains `pending` rows (woken by NOTIFY, with
-- a periodic poll as a backstop) and marks them done; on startup it drains
-- anything that arrived while it was down — so nothing is ever lost.
--
-- NON-OBVIOUS DECISIONS:
--   * This is an OPERATIONAL QUEUE, not provenance. It shares the DB for
--     transactional atomicity with the version/publish insert, but it is NOT one
--     of the 7 UL tables and carries no lineage (ADR 0018/0019).
--   * NO trigger emits the event. The WRITER (Submitter) does the INSERT + NOTIFY
--     in its app transaction; the DB does no orchestration / no triggers
--     (consistent with ADR 0008 and the trigger-free counters in 0001).
--   * UNIQUE(type, subject_id) makes EMISSION idempotent — one event per take
--     landing (subject = versions.id) / per publish (subject = publishes.id). The
--     Submitter inserts ON CONFLICT (type, subject_id) DO NOTHING.
--   * Delivery is at-least-once, so the Roustabout's HANDLERS must be idempotent
--     (ADR 0019): proxy/log are overwrite-safe; auto-publish/chain guard on their
--     own unique keys (e.g. publishes UNIQUE(shot_code, number)).
--
-- NOTIFY channel contract: 'fleet_events'. Payload is just a wakeup hint (the
-- event's subject_id as text); the Roustabout ignores it and drains the table, so
-- a missed/garbled NOTIFY never loses work. The Submitter MUST NOTIFY this
-- channel; the Roustabout LISTENs on it.
-- ============================================================================

BEGIN;

CREATE TABLE events (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    type          text        NOT NULL
                  CHECK (type IN ('VersionRecorded','PublishRecorded')),   -- ADR 0013/0018
    subject_id    uuid        NOT NULL,        -- VersionRecorded: versions.id · PublishRecorded: publishes.id
    payload       jsonb       NOT NULL DEFAULT '{}'::jsonb,   -- denormalized dispatch context the Roustabout
                                               --   needs (shot_code, run_id, run_type, role/tag, ...) so a
                                               --   handler needn't re-query just to route
    status        text        NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','done','error')),
    attempts      integer     NOT NULL DEFAULT 0,    -- bumped on each failed handler run
    last_error    text,                              -- last handler exception repr (for inspection)
    created_at    timestamptz NOT NULL DEFAULT now(),
    processed_at  timestamptz,                       -- set when status -> 'done'
    UNIQUE (type, subject_id)                        -- emission idempotency: one event per subject
);

-- The drain query is "oldest pending first". A PARTIAL index keeps it tiny (only
-- unprocessed rows) and backs SELECT ... WHERE status='pending' ... FOR UPDATE
-- SKIP LOCKED.
CREATE INDEX events_pending_idx ON events (created_at) WHERE status = 'pending';

COMMIT;
