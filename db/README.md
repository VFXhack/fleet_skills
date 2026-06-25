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
