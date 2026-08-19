# ADR 0027 — The provenance schema must map 1:1 onto AYON's entity model (design constraint, no AYON code)

**Status:** Accepted
**Date:** 2026-08-19 (Session R2; drafted R1)
**Refines:** ADR 0005, ADR 0011 · **Relates:** ADR 0008 (AYON rejected as the core — unchanged)

## Context
ADR 0008 rightly rejected adopting AYON as the provenance core. But AYON is now real in
the business: a test server runs on huxley (:5000), GC_grayscale runs on the promise
server's AYON, and the accepted Promise pitch makes "Bid-to-AYON bootstrap" a committed
demo. Phase 2 will auto-publish shotgate keeps to AYON. If the schema drifts from AYON's
shape, that integration becomes a migration; if it maps, it's an exporter.

## Decision
A standing **design constraint** on the provenance schema (checked at every migration):

| fleet_skills | AYON | Note |
|---|---|---|
| Project (`job_code`) | project | |
| Episode / Sequence / Shot (codes) | folder hierarchy | codes ↔ folder paths |
| Run + Version (`v###`) | workfile-side iterations | pre-publish; AYON never sees them |
| **Publish (`p###`)** | **product + version** | our gate = AYON's only unit; product name ≈ stage/Role |
| Delivery (client `v#`) | delivered/approved status on a version | |
| Version files (address, proxy) | representations | |
| frozen_submission / recipe | version attribs / metadata | travels as attribute payload |

- No AYON code in phase 1. The constraint is a review check: any schema change that has
  no AYON counterpart needs an explicit "phase-2 exporter handles it" note in its ADR.
- Shotgate verdicts (ADR 0026) are the publish events an AYON publisher will subscribe to.

## Consequences
Phase-2 AYON publisher is a mapping exercise, not a migration. The Promise demo
(bid → project bootstrap → publishes appearing in AYON) rides the same pipe as internal
provenance.

## Why an ADR
It binds every future migration to an external model we've committed to integrating with,
before drift can accumulate — cheap to honor now, expensive to retrofit later.
