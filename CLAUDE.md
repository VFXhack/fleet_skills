# fleet_skills — the pipeline system (reconciliation in progress)

Canonical home: **watts `D:\Tools\dev\fleet_skills`** (github VFXhack/fleet_skills;
leary keeps a clone; git is the mirror). Fleet-wide machine facts live in
`~/.claude/CLAUDE.md`, not here.

## Session start — read in this order

1. `RECONCILIATION_BRIEF.md` — the 12 grilled decisions + rulings R-1..R-6 +
   the **R2 agenda** (current next steps live there, including Andy's four
   shotgate-contract hardening questions).
2. `ADR_REALITY_AUDIT.md` — per-ADR verdicts + draft ADRs 0025–0027.
3. `HANDOFF.md` — Session 13 build state (submitter expand, dry dispatch).
4. `CONTEXT.md` — the ubiquitous language. `PIPELINE.md` — the flow.

## State that is NOT in this repo

- Prod DB: `fleet` on mckenna Postgres (DSN in `~/.fleet/config.toml` per
  host; watts + leary have it). **At migration 0003, all tables empty, no
  backup job** — applying 0004/0005 + a pg_dump timer are R2 openers.
- Test DB discipline: `db/test_db.sh` — destructive ops refuse any
  non-`fleet_test` DSN.
- The watts clone has **no venv yet** — `pip install -e .` before running CLIs.
- shotgate (the review bounded context, per draft ADR 0026) lives at
  `D:\Tools\shotgate`, v1.3.0, serves http://watts:8377.

## Rules of the road

- Decisions get grilled with Andy before code (AskUserQuestion, one at a time,
  recommendation first). Approved decisions land in the brief or a numbered ADR.
- Spine changes wait for their phase; daily-driver friction (shotgate UX, tool
  bugs) gets fixed immediately — it never touches the ADR seams.
- KG updates go through the `kg-sync` skill (per-host SQLite ×4). Palace gets
  a decisions drawer per phase milestone.
