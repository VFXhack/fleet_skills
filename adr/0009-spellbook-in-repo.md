# ADR 0009 — Spellbook lives as a folder in this repo (rides the existing Git remote across the Fleet)

**Status:** Accepted
**Date:** 2026-06-25

## Context
Branch 3. The **Spellbook** (project-agnostic craft: **Spells** = procedures, plus **Templates** built
from **Blocks** = verified prompt patterns) currently lives in **Notion**, and CONTEXT.md flagged it as
"migrating toward Git." Three homes were on the table:

1. **A folder in this repo** (`fleet_skills`), beside `skills/`.
2. **A separate repo** (`fleet_spellbook`).
3. **Stay in Notion** with a one-way sync to a Git mirror.

A hard constraint surfaced: the Spellbook must be **available and wired to work on every workstation**
(Watts, Leary), not just wherever it was authored.

Decisive facts:
- The glossary already locks a **maturity continuum**: a **Spell graduates into a Skill** when it's
  invoked often enough to harden. **Skills already live in this repo** under `skills/`. Co-locating
  Spells makes graduation a **move within one repo**, not a cross-repo migration.
- The **storage rule** (CONTEXT.md) already routes *code / skills / docs / decisions → Git*. Spells and
  Templates are authored craft/docs — they belong on the Git side, not a media store.
- This repo **already has a cloud Git remote** (`github.com/VFXhack/fleet_skills`, `main` tracks
  `origin/main`). So cross-machine availability is an **already-solved** problem: clone + `git pull`.
- Keeping Notion as the source of truth would re-introduce the exact coupling we just **rejected for the
  provenance DB** (ADR 0008): Notion as truth, plus sync to build and maintain.

## Decision
The **Spellbook is a top-level `spellbook/` folder inside this repo** (`fleet_skills`), beside `skills/`:

```
fleet_skills/
  skills/            <- hardened, atomic Claude Code skills
  spellbook/
    spells/          <- procedures (recipes; may invoke Skills + human steps)
    templates/       <- verified prompt patterns
      blocks/        <- model/function-specific prompt fragments (+ variants)
  adr/   CONTEXT.md
```

- **Distribution = the existing Git remote.** Each workstation clones `fleet_skills` from GitHub and
  `git pull`s to stay current; the Spellbook rides along with the repo. No separate Spellbook sync.
- **Staying current is manual (`git pull`) for now.** Acceptable for a solo operator; automation is
  deferred until the manual step demonstrably bites.
- **Notion stops being the Spellbook's source of truth.** Existing Spellbook content migrates into
  `spellbook/`; a Notion read-mirror is optional and out of scope here.
- **Spell → Skill graduation** is a file move `spellbook/spells/<x>` → `skills/<x>` within this repo.

## Consequences
- **Per-machine wiring is a deferred-config item:** a known clone path per workstation (a logical "fleet
  repo root" resolved per machine, same pattern as `base_path` / the Postgres DSN) so tools and Claude
  Code reliably find `skills/` + `spellbook/`. Recorded next to the Huxley share name; not blocking.
- **A migration task is implied:** move the current Notion Spellbook content into `spellbook/` (format
  TBD — Markdown for Spells; Template/Block representation to be settled in a later branch).
- The glossary's "Currently in Notion; migrating toward Git" softens to a **concrete home**.
- No change to the **provenance DB** (ADR 0008) — that's the dynamic ledger; the Spellbook is static craft.

## Why an ADR
"Where does the reusable craft live" is a boundary every authoring tool and the Spell→Skill lifecycle
depend on, and it rejected two plausible defaults (separate repo; keep Notion). It reverses with real
cost (re-homing content + repointing tools), so the reasoning is on record.
