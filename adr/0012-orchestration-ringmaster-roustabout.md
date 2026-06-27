# ADR 0012 — Orchestration is two named floors: Ringmaster (agent) over Roustabout (deterministic worker); Griptape demoted

**Status:** Accepted
**Date:** 2026-06-25
**Amends:** ADR 0010
**Amended by:** ADR 0013 (the `VersionRecorded` seam — the event fires after the take lands; the
Submitter, not the Roustabout, writes the output address)

## Context
Re-opened Branch 5. ADR 0010 named **Griptape** "the conductor" — one orchestration layer above an
atomic Submitter, joined at **`VersionRecorded`**, with **Hermes** (Ramdass) set to "drive Griptape
flows" later. A grilling session pressure-tested that and surfaced two problems:

1. **"Orchestration" was carrying two different jobs.** Reacting to an event with a fixed, branchy,
   **no-LLM** flow (render proxy → write pointer → chain next stage) is a *different* job from an agent
   that **looks at output and decides** what to do (quality, which take to promote, what next). ADR 0010
   bundled both under one name and one tool.
2. **Griptape is the wrong class of tool for the deterministic job.** The Griptape docs (read this
   session) confirm it is primarily an **LLM/agent framework** — Structures (`Agent`/`Pipeline`/
   `Workflow`), Tasks (`PromptTask`, `CodeExecutionTask`), an Event-Listener system. It *can* run a
   non-LLM `Workflow`, but its whole grain is prompts / RAG / agents. Using it for dumb plumbing is a
   heavy framework run at ~10% utilisation, against its grain.

Andy is a solo operator still levelling up on code; today's actual pain is hand-running `run_*.ps1` +
manual Notion logging. The honest near-term need is **deterministic glue**, not an agent. He explicitly
chose the orchestration ceiling as **"branchy but rule-based"** (a decision tree he writes), with all
*judgment* living a floor up.

Alternatives weighed for the deterministic floor: a **real workflow engine now** (Prefect / Temporal /
Windmill / Dagster), **n8n** (visual, but logic lives outside Git — fights the Git-canonical rule),
**Griptape** (wrong floor), and a **thin Python worker** (chosen).

## Decision
Split the orchestration side into **two named role-floors**, joined to the Submitter at the **same
`VersionRecorded` seam** that ADR 0010 fixed (that seam is preserved). The metaphor family is **the
Circus**: a Ringmaster directs the show; Roustabouts rig between acts.

- **Roustabout — the deterministic floor (now).** Subscribes to events (starting with
  `VersionRecorded`), **branches by `run.type` / Role / stage**, and runs a **pre-wired flow**: render
  the proxy/thumbnail, write the pointer back, log, notify, chain next stages. **No LLM, no judgment** —
  if a step ever needs to *judge*, that logic belongs **up** in the Ringmaster. It **calls** the
  Submitter as one instrument; it is not the Submitter. Filled today by a **thin Python worker**
  (Postgres `LISTEN/NOTIFY` + a `FLOWS[run.type]` dispatch table). It **graduates** to a real workflow
  engine only when hand-rolled retries / observability start hurting — the same "earn the hardening"
  rule as **Spell → Skill**.
- **Ringmaster — the agent floor (later).** Looks at outputs and **decides** (quality, which take to
  promote, what next), drives multi-step flows, and talks to Andy. The role the future **Hermes** agent
  (earmarked for **Ramdass**) plays. Tooling is **TBD** — **Griptape** *or* the **Claude Agent SDK** are
  the candidates; not decided here. It sits **above** the Roustabout and is **deferred** — only the
  Roustabout exists today.

## Consequences
- **Griptape is demoted** from "the conductor" to *a candidate tool for the Ringmaster floor* — and is
  explicitly **not** the Roustabout. In effect it moved **up** a floor from where ADR 0010 placed it.
- **The role is named for the job, not the tool.** "Griptape" is no longer a domain noun; the
  glossary nouns are **Ringmaster** and **Roustabout**, whose implementations can change underneath them
  (thin worker → Prefect; Griptape → Claude SDK) without renaming the concept.
- **ADR 0010's core stands:** atomic Submitter; the seam is the `VersionRecorded` event; **no
  orchestration in the Submitter or the DB**. This ADR only splits the "conductor" in two and re-assigns
  the tools.
- **The Roustabout ↔ Ringmaster seam is internal and deferred.** The Ringmaster plugs in above the
  Roustabout later without re-cutting the Submitter or the event contract.
- The Roustabout stays **small and testable**; the agentic floor can grow (Hermes) without touching it
  or the ledger-writer.

## Why an ADR
It amends an **Accepted** ADR (0010) by demoting its headline tool choice and renaming its central
concept — a future reader will otherwise find "Griptape = the conductor" in 0010 and the old glossary and
be confused. Re-cutting the two floors later means re-touching the event contract, so the split, the
names, and Griptape's demotion are on record.
