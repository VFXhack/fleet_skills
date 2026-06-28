-- Reset the Fleet TEST database to empty (see db/README.md -> "Test database").
--
-- Blunt teardown: truncates every UL table in one statement, resets identity
-- sequences, and CASCADEs so FK order never matters. This is the whole point of a
-- separate test DB -- no surgical, scoped DELETEs like prod cleanup needs.
--
-- SAFETY: this file is only ever run by `db/test_db.sh reset`, which refuses to
-- run unless the resolved DSN targets a database literally named `fleet_test`.
TRUNCATE projects, runs, versions, publishes, deliveries, assets, bindings, events
    RESTART IDENTITY CASCADE;
