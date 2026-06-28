# Fleet provenance core (Postgres)

The system of record for all provenance — the `runs → versions → publishes → deliveries`
pointer-graph plus asset-binding edges, with a JSONB frozen-submission per Version. See
**ADR 0008** (why Postgres on Mckenna), **ADR 0005** (artifact/versioning model), **ADR 0007**
(recipe storage), and `CONTEXT.md` → *Provenance store*.

## Where it lives
- **Host:** Mckenna (Ubuntu 25.10), the Fleet DB host. Postgres 17.
- **Database:** `fleet`. Schema = the 7 UL tables in `migrations/`.
- **Reachability:** listens on `localhost` + Mckenna's Tailscale IP (`100.108.34.23:5432`);
  `pg_hba` allows the tailnet (`100.64.0.0/10`) for role `fleet` with `scram-sha-256`.

## How tools connect (DSN resolution)
Fleet tools (`create-project`, the Submitter, runners) resolve the DSN in this order:
1. `FLEET_DB_DSN` environment variable, else
2. `~/.fleet/config.toml` → `[db].dsn`.

`~/.fleet/config.toml` is **per-machine and never committed** (it holds the password). The
`fleet` login role has DML on all tables in `public` (and `CREATE` on the schema for future
migrations). Superuser (`postgres`) is socket-only on Mckenna.

## Migrations
Plain SQL files in `migrations/`, applied in numeric order, each wrapped in a single
transaction. Current:
- `0001_initial_schema.sql` — the 7 tables (`projects`, `runs`, `versions`, `publishes`,
  `deliveries`, `assets`, `bindings`), per-gate counters as `UNIQUE(shot_code, n)`, FK
  lineage edges, JSONB `frozen_submission` on `versions`.

Apply a migration (from Mckenna, as superuser — pipe over stdin so `postgres` needn't read
your home dir):
```bash
sudo -u postgres psql -d fleet < migrations/0001_initial_schema.sql
```
Or, once a client with the `fleet` DSN is set up, apply over the network as the `fleet` role.

## Test database (`fleet_test`)

**All testing runs against a separate `fleet_test` database — never prod `fleet`.** This is the
isolation boundary: test rows physically cannot mix with real ones, teardown is a blunt `TRUNCATE`
(not a surgical scoped delete), and the connection recipe is committed so no session re-discovers it.

- **Same Mckenna cluster**, same schema (migrations `0001`–`0003` applied), owned by the `fleet`
  role (granted `CREATEDB` once, 2026-06-28, so it can self-serve test DBs over the network).
- **Helper:** `db/test_db.sh` (run where `psql` is reachable — on Mckenna, or any tailnet box with
  `psql`). Resolves the test DSN from `$FLEET_TEST_DSN`, else the prod `[db].dsn` in
  `~/.fleet/config.toml` with the database name swapped to `fleet_test`.

  | Command | Does |
  |---|---|
  | `bash db/test_db.sh setup` | create `fleet_test` if absent + apply all migrations |
  | `bash db/test_db.sh reset` | `TRUNCATE` every table back to empty (the fast teardown) |
  | `bash db/test_db.sh info`  | row counts per table |
  | `bash db/test_db.sh dsn`   | print the resolved test DSN |
  | `bash db/test_db.sh psql`  | psql shell against `fleet_test` |

- **Point a tool at the test DB:** tools resolve `FLEET_DB_DSN` before the config file, so
  `export FLEET_DB_DSN="$(bash db/test_db.sh dsn)"` (or on Windows, set `$env:FLEET_DB_DSN` to the
  `…/fleet_test` DSN) makes `create-project` / the Submitter write to `fleet_test`. Unset it to hit prod.
- **Safety:** every destructive op in the helper asserts the resolved DSN targets `fleet_test`; pointed
  at prod it refuses and exits non-zero. Verified 2026-06-28.
