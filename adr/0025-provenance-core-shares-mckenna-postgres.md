# ADR 0025 — The provenance core shares Mckenna's Postgres with MemPalace; backup becomes a prerequisite

**Status:** Accepted
**Date:** 2026-08-19 (Session R2; drafted R1)
**Amends:** ADR 0008 (placement confirmed, coexistence + ops added)

## Context
ADR 0008 placed the provenance core on Mckenna Postgres; Session 8 stood it up (PG 17,
db `fleet`). Since then Mckenna also became home to the MemPalace fleet store (pgvector,
~532k drawers) and the Apricity dashboard. Two data systems with different jobs now share
one host — and the reconciliation brief (decision 10) requires the boundary stated and
the host backed up.

Ops verification (R-6, 2026-08-18): prod `fleet` is live on mckenna (PG 17.10, tailnet
100.108.34.23) at **migration 0003** with all tables empty; `mempalace` confirmed on the
same cluster; **no automated pg backup exists**; `~/.fleet/config.toml` present on watts
and leary.

## Decision
- The provenance core remains db **`fleet`** on Mckenna's PG 17 cluster, coexisting with
  MemPalace's database(s). One cluster, separate databases, separate roles.
- **Boundary:** Postgres `fleet` holds **records** (runs/versions/publishes/deliveries —
  structured, queryable, relational). MemPalace holds **narrative** (verdicts-as-prose,
  decisions, gotchas) fed by fleet_mine. Run records are never drawers; drawers are never
  provenance. A provenance report reads `fleet` and may *cite* palace drawers.
- Artifacts stay file-based (the project store per ADR 0028); the DB stores addresses,
  never pixels.
- **Prerequisite:** a real Mckenna backup story (nightly `pg_dump` of `fleet` + the
  palace DB to a second host at minimum) lands before the proving lane goes live.

## Consequences
Mckenna is formally state-critical; its provisioning/backup is part of phase 1.
`fleet` migration state must be brought to 0005 (verified safe: all tables empty)
before new writes.

## Why an ADR
It formalizes a shared-host coexistence that would otherwise look accidental, states the
records-vs-narrative boundary every reporting tool depends on, and turns "back up mckenna"
from a wish into a phase-1 gate.
