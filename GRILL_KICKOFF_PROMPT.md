# Grill session — kickoff prompt

Paste everything in the box below into the fresh Claude Code session (started from the
root of your local `fleet-skills` clone).

---

```
Read HANDOFF.md, CONTEXT.md, and adr/0001-skills-vs-spells.md in full before responding.

Then run /grill-with-docs to help me harden the ubiquitous language and foundations of
this CG → AI production pipeline. This repo (fleet-skills) is the bounded context; its
CONTEXT.md is the glossary and the source of truth.

Rules for the session:
- Don't write pipeline code yet. Language and structure first.
- Grill me one branch at a time. Resolve dependencies before moving on.
- When my language is fuzzy, challenge it against CONTEXT.md, propose 2–3 concrete
  options with your recommendation, and let me choose.
- As decisions land, UPDATE CONTEXT.md directly. For any non-obvious, hard-to-reverse
  decision, write an ADR in /adr (numbered, following 0001's format).
- Keep me moving — I have ADHD, so one question at a time and concrete next steps.

Start with the open questions in HANDOFF.md, in this priority order:
1. Project base_path on the Fleet drive.
2. Manifest schema (fields + versioning) — this feeds the Submitter.
3. Spellbook location after migrating from Notion.
4. Project index: flat file vs. a table in Mckenna's DB.
5. Whether Griptape is the Submitter's orchestration layer.
6. The real depth-pass method (to replace the TODOs in skills/depth-pass/SKILL.md).

Begin by confirming you've read the three files and giving me a one-line summary of the
current ubiquitous language, then ask me your first question.
```

---

**Tip:** if you'd rather establish language before the repo feels like "a codebase,"
`/grill-me` works too — but since we already have files here, `/grill-with-docs` is the
right call (it reads and updates CONTEXT.md + ADRs as you go).
