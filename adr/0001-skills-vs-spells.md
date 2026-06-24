# ADR 0001 — Skills vs. Spells, and renaming the cookbook to the Spellbook

**Status:** Accepted
**Date:** 2026-06-24

## Context
The system has two different kinds of reusable knowledge that were being conflated:
atomic, callable capabilities vs. multi-step recipes. Without distinct words for them,
language stayed fuzzy and the AI kept re-describing things verbosely.

## Decision
- A **Skill** is an atomic Claude Code capability (a `SKILL.md`), invoked by name, living
  in the `fleet-skills` repo.
- A **Spell** is an entry in the **Spellbook** — a documented recipe / collection of
  actions, which may invoke one or more Skills and may include manual steps.
- The **"cookbook" is renamed to the "Spellbook."** Each entry is a Spell.
- A **Spell graduates into a Skill** when it's invoked often enough to be worth hardening.
- A **Skill never depends on a Spell** (skills stay atomic and reusable).

## Consequences
- Clear promotion path: method → Spell (write it down) → Skill (harden it) when usage justifies.
- The Spellbook becomes the staging ground; `fleet-skills` becomes the hardened library.
- Open: where the Spellbook physically lives after migrating from Notion (folder in this
  repo vs. separate repo vs. Notion + sync) — to be decided early in the build.

## Why an ADR
This is a naming + structural decision that touches every file and variable name going
forward, and reversing it later would be expensive. That's the bar for an ADR.
