# HANDOFF — for the fresh Claude Code agent

You are picking up a **domain-driven design** effort to harden a scattered CG → AI video
production pipeline into a clean system of **Skills** and **Spells**. Read this, then read
`CONTEXT.md` and `adr/0001-skills-vs-spells.md` before doing anything.

## Who / what
- **Andy** — solo operator, building this while also doing client work and learning to code.
  He has ADHD; favor concrete next steps, one thing at a time, no sprawling tangents.
- **This repo (`fleet-skills`)** — the canonical, version-controlled home for **Skills**.
  Heavy media never lives here; it stays on the **Fleet** drive, referenced by per-Project manifests.

## The goal of THIS session
Run a **`grill-with-docs`** session to sharpen the ubiquitous language and lock the
foundations *before* building. Specifically:
1. Interview Andy to resolve the fuzzy/open items (see below).
2. Update `CONTEXT.md` as decisions land.
3. Write an **ADR** for any non-obvious, hard-to-reverse decision.
Do **not** start writing pipeline code this session. Language and structure first.

## Current state (already decided — don't re-litigate)
- **Skill** = atomic Claude Code capability (SKILL.md), lives here. Invoked by name.
- **Spell** = a recipe in the **Spellbook** (the cookbook, renamed). May invoke Skills + manual steps.
- A **Spell graduates into a Skill** when invoked often; a **Skill never depends on a Spell**.
- **Storage rule:** code/skills/docs/decisions → Git; heavy media → Fleet drive (rendered via
  Flamenco on Mckenna), referenced by the **Manifest**. Never mix.
- **Mckenna** = Fleet machine hosting the DBs + running the **Flamenco** render queue.
- **Submitter** = ingests → logs → passes; logs Runs to Mckenna's DB, dispatches renders to Flamenco.
- First two skills drafted: `create-project`, `depth-pass` (templates with TODOs).

## Open questions to grill Andy on
1. **Project base_path** on the Fleet drive — where do Projects physically live?
2. **Manifest schema** — what fields does `manifest.json` need? Versioned how? (feeds the Submitter ADR)
3. **Spellbook location after migration** — folder in this repo, separate repo, or Notion + sync?
4. **Project index** — flat file vs. a table in Mckenna's DB?
5. **Griptape** — is it the Submitter's orchestration layer, or separate? (likely an ADR)
6. **depth-pass method** — pull the real steps out of his head / the Spellbook to replace the TODOs.

## How to behave
- Grill one branch at a time; resolve dependencies before moving on.
- When language is fuzzy, propose 2–3 concrete options with a recommendation, then let Andy choose.
- Cross-reference any existing pipeline code Andy points you at, to ground terms in reality.
- Update `CONTEXT.md` and `/adr` as you go — don't leave decisions only in chat.
- End with: what changed in CONTEXT.md, which ADRs were written, and the single next action.
