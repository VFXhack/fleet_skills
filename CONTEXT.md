# CONTEXT.md — Fleet Production System

> This is the **ubiquitous language** for the Fleet production pipeline: the shared
> glossary used by the code, by Andy, and by any AI agent working in this repo.
> It is the source of truth for what words *mean*. Keep it tight. Sharpen terms here
> via `grill-with-docs` sessions; record non-obvious decisions as ADRs in `/adr`.
>
> **Status:** Seed draft (v0.1, 2026-06-24). To be grilled and refined in Session 1.

---

## Glossary

### Skill
A **Claude Code skill**: a single, atomic, callable capability with a `SKILL.md`
(name, when-to-use trigger, inputs, steps, outputs). Reusable and invoked by name.
Lives in this repo under `skills/`. Skills are the *hardened* units of the system.

### Spell
An entry in the **Spellbook**: a documented recipe — a collection of actions (manual
+ automated) to achieve an outcome. A spell may **invoke one or more Skills** and may
include human steps. Spells are the *working* layer where methods first get written down.
- A **Spell graduates into a Skill** when it's invoked often enough to be worth hardening.
- A **Spell may contain Skills**, but a **Skill never depends on a Spell** (skills stay atomic).

### Spellbook
The collection of all Spells. **Formerly called the "cookbook"** — renamed to Spellbook.
Currently lives in Notion; migrating toward this GitHub repo. **Each entry = one Spell.**

### Project
A bounded piece of production work (a shot, sequence, or deliverable) with its own
folder, `manifest.json`, and `CONTEXT.md`. Created via the `create-project` skill.

### Submitter
The connective tissue of the pipeline: **ingests** information → **logs** it →
**passes** it to the next step. Logs Runs to the database on **Mckenna**; dispatches
heavy render work to **Flamenco**.

### Run
One logged execution of a Skill or pipeline step against a Project — captured with its
inputs, params, and output locations. Recorded by the Submitter.

### Manifest
The per-Project record (`manifest.json`) that maps **Git ↔ drive ↔ render outputs**.
The single map the Submitter reads/writes so heavy media never has to live in Git.

### Depth Pass
A depth-map reference generated from a plate/frame, used to guide gen-AI video.
The first hardened Skill (`depth-pass`).

### Mckenna
A machine on **Fleet** that **hosts the databases** and **runs the Flamenco render
queue**. The Submitter writes Run logs to Mckenna's DB; heavy gen/render jobs are
dispatched to Flamenco on Mckenna.

### Flamenco
The render queue / farm manager running on Mckenna. Where heavy render and gen jobs
are submitted and tracked.

### Fleet
The overall machine + storage system (the network of boxes and drives, including Mckenna).

### Context (DDD)
A bounded area that speaks one shared language, documented in a `CONTEXT.md`.
Right now the whole system is one Context; split into a context-map only if it grows.

### ADR — Architectural Decision Record
A short markdown file in `/adr` capturing a **non-obvious, hard-to-reverse decision**
and *why*. Write one only when a choice is surprising-without-context or has real
trade-offs downstream.

---

## Relationships & rules

- A **Spell** may invoke one or more **Skills**; a **Skill** never depends on a Spell.
- A **Spell** graduates to a **Skill** when invoked frequently.
- **Skills** live in Git (this repo). **Spells** live in the **Spellbook** (Notion → Git).
- The **Submitter** logs **Runs** to the DB on **Mckenna** and dispatches renders to **Flamenco**.
- **Storage rule:** code / skills / docs / decisions → **Git**. Heavy binary media →
  **Fleet drive**, rendered via **Flamenco on Mckenna**, referenced by the **Manifest**.
  Never mix the two.

---

## Open questions (to resolve via grilling / ADRs)
- Does **Griptape** become the Submitter's orchestration layer, or stay separate? (→ ADR)
- What is the **Manifest schema** (fields, versioning)? (→ ADR in Session 5)
- Where does the **Spellbook** physically live once migrated — a folder in this repo,
  a separate repo, or stays in Notion with a sync? (→ decide early)
- Naming: confirmed **"skill"** for Claude Code skills, **"spell"** for Spellbook entries. ✅
