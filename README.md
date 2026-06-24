# fleet-skills

Canonical source of truth for **Skills** in the Fleet production pipeline (CG → AI video).

This repo is version-controlled and cloned locally. Heavy media never lives here — it
stays on the Fleet drive and is referenced by each Project's `manifest.json`.

## What's here
- **`CONTEXT.md`** — the ubiquitous language (read this first; it defines every term).
- **`skills/`** — one folder per Skill, each with a `SKILL.md`.
  - `create-project/` — scaffolds a new Project folder.
  - `depth-pass/` — generates a depth-pass reference for gen-AI video.
- **`adr/`** — Architectural Decision Records (non-obvious, hard-to-reverse decisions).
- **`HANDOFF.md`** — context brief for a fresh Claude Code agent.
- **`GRILL_KICKOFF_PROMPT.md`** — paste this to start a grill-with-docs session.
- **`SETUP-GRILL-SESSION.md`** — step-by-step to get the grill session running.

## Key terms (full definitions in CONTEXT.md)
- **Skill** = atomic Claude Code capability (lives here).
- **Spell** = a recipe in the **Spellbook** (the renamed cookbook); can invoke skills.
- **Submitter** = ingests → logs → passes; logs to **Mckenna**, renders via **Flamenco**.
- **Mckenna** = Fleet machine hosting the DBs + Flamenco render queue.

## Convention
A method gets written first as a **Spell** in the Spellbook. When it's invoked often
enough, it **graduates into a Skill** here.
