# ADR 0007 — Recipe storage: hybrid (shared recipe on the Run, frozen Submission Prompt per Version)

**Status:** Accepted
**Date:** 2026-06-24

## Context
ADR 0005 left a latent tension: a **Run** "records the recipe" *and* each **Version** "carries its
full recipe." A **Seed Sweep** makes N Versions that share everything but the seed, so two naive
readings both fail:
- **Run-only** (Versions hold just a seed + pointer) can't faithfully reproduce a take if the
  **Spellbook Template** that authored it is later rewritten — the resolved string is gone.
- **Per-Version full copy** duplicates the shared recipe N times for no benefit.

The **Version's invariant is reproducibility** (Andy, this session): everything needed to recreate a
take from scratch must be consistent in one record, and must survive later Spellbook edits. The two
sit at **different abstraction levels** — what we *asked for* vs. what we *literally sent* — which is
the key the naive readings miss.

## Decision
Store the recipe in **two parts**, by level:

- **Run = the recipe (authoring level).** The shared, sweep-wide intent recorded **once** on the Run:
  the **Template** reference, the `{asset → pinned Publish/Import, role}` **bindings**, model/tier/mode,
  and the flat params common to the sweep.
- **Version = the frozen submission (resolved level).** Each Version stores a pointer up to its Run,
  its **delta** (the swept value, e.g. the seed), and a **frozen Submission Prompt + resolved params** —
  the exact, model-specific payload actually sent to Fal / Comfy / Flamenco.

The frozen submission is an **immutable value object**: written once at Submit time, never edited, and
**sufficient on its own** to reproduce the take. The **Spellbook is launch-time convenience, not on the
reproducibility critical path** — re-authoring a Template can never invalidate an existing Version.

This satisfies 0005's "Version carries its full recipe" precisely:
**Version's full recipe = (pointer to the Run's shared recipe) + (its own frozen Submission Prompt + delta).**

## Consequences
- **Storage shape (feeds ADR 0008):** a normalized `runs → versions` relation, plus a **JSON(B)
  column on `versions`** holding the frozen submission. Sweeps store 1 recipe + N small rows, each
  self-reproducing.
- The **core domain output** (a Submission Prompt — see CONTEXT.md) is now what gets *frozen* per take;
  provenance and the core craft line up.
- Reproducing a Version **never reads current Spellbook/Template state**.
- Proxy/thumbnail are **derived** from the Version via a `VersionRecorded` event — orchestration, not
  storage (Branch 5 / Griptape). No DB trigger renders the proxy.
- `Recipe` earns a precise two-part meaning in the glossary (see findings packet).

## Why an ADR
This fixes exactly *what is stored where* for every take, and it is load-bearing for both the DB schema
(ADR 0008) and the pipeline's reproducibility guarantee. It reverses expensively (re-backfilling every
Version's frozen payload) and resolves an ambiguity a reader of 0005 would otherwise hit head-on.
