# ADR 0010 — Griptape is a separate orchestration layer (conductor), not part of the Submitter

**Status:** Accepted — **amended by ADR 0012** (the single "Griptape conductor" is split into two floors,
**Ringmaster** (agent) over **Roustabout** (deterministic worker); Griptape is demoted from "the conductor"
to a *candidate tool for the Ringmaster floor*, and is **not** the Roustabout. The seam decision below — atomic
Submitter, joined at `VersionRecorded`, no orchestration in the Submitter or DB — **still stands**.)
**Also amended by ADR 0013** — *who writes the output address, and when the event fires*: the Submitter
writes `versions.address` on render completion and emits `VersionRecorded` **then** (not at dispatch);
"write the pointer back" moves **off** the Roustabout.
**Date:** 2026-06-25

## Context
Branch 5. ADR 0008 already placed **Griptape** on "the conductor side of the wall" — the thing that
handles the **`VersionRecorded`** event (renders the proxy, writes the pointer back) — and kept
**orchestration out of the DB** (no domain-doing triggers). It also cited AYON's event-driven
**Workflows** as a *reference design* for this layer. What 0008 left open was the **seam**: is Griptape
the *same software* as the **Submitter**, or a *separate piece* that talks to it via the event?

Griptape is a Python framework for building **agent / tool workflows** — sequencing tasks and reacting
to events. That is **orchestration**, a different job from what the Submitter does (validate a brief →
write the Run/Version to Postgres → dispatch to Flamenco). Three seams were considered: (A) separate
conductor above an atomic Submitter; (B) Griptape as the engine *inside* the Submitter; (C) one engine
with two named roles (sync submit-path + async post-event).

## Decision
**Griptape is a separate orchestration layer — the conductor — and the Submitter is an atomic tool it
does not live inside.**

- **The Submitter is atomic:** ingest a brief/recipe → **write** the Run/Version to the **Postgres
  provenance store** on Mckenna → **dispatch** heavy render to **Flamenco** → **emit `VersionRecorded`**.
  It does **no** downstream orchestration.
- **Griptape is the conductor:** it **subscribes to events** (starting with `VersionRecorded`),
  **sequences Skills and Spells** into flows, renders the **proxy/thumbnail**, **writes the pointer
  back**, and drives **next steps** (publish prep, notifications, stage chaining). It calls the Submitter
  as one instrument; it is not the Submitter.
- **The seam is the event.** The synchronous write-path (Submitter) and the asynchronous post-processing
  (Griptape) are decoupled at `VersionRecorded` — never via a shared in-process call graph and never via
  a DB trigger.
- **Hermes** — the future agent earmarked for **Ramdass** — is the agent that *drives* Griptape flows
  once the structure exists; it plugs in on the conductor side.
- **AYON Workflows** remains a **reference design** for this layer (per ADR 0008), not an adopted system.

## Consequences
- **An event mechanism is implied** (how `VersionRecorded` is emitted after the write commits and how
  Griptape consumes it — Postgres `LISTEN/NOTIFY`, a queue, or Griptape polling). Implementation detail,
  **deferred**; the contract ("Submitter emits after commit; Griptape reacts") is what's fixed here.
- **Where Griptape runs is deployment detail, deferred** (Mckenna alongside the controller, or with
  Hermes on Ramdass later) — not a domain decision.
- **Skills stay atomic and orchestration-free** — consistent with the Skill philosophy (CONTEXT.md):
  Griptape sequences them; they don't sequence each other.
- The Submitter stays **small and testable**; orchestration can grow agentic (Hermes) without touching
  the ledger-writer.
- Reinforces the ADR 0008 wall: **no next-step logic in the Submitter or in the DB.**

## Why an ADR
The Submitter↔Griptape seam is a boundary every downstream behavior crosses (proxy, publish prep,
notifications, future agentic flows), and it rejected the tempting "just build the Submitter on Griptape"
shortcut. Moving the seam later means re-cutting the Submitter and the event contract, so the choice is
on record.
