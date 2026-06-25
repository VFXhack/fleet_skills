# ADR 0005 — Artifact, versioning & provenance model (gated namespaces + lineage)

**Status:** Accepted
**Date:** 2026-06-24

## Context
VFX overloads the word **version** — it is used for every iteration at every stage, which makes
provenance ambiguous. The concrete failure: a Run produces ~25 takes; one is promoted for internal
review; after several internal note rounds a take is approved and sent to the client. If a single
version number is carried the whole way, the client sees "v50" of a shot they have never seen, and
internal churn leaks across the client boundary. Carrying numbers across gates is the bug.

A prior UL session locked **Generation** for a take and **Publish** for a promoted take, and made
**Submit** the act. But (a) the domain expert ruled **Version** is the correct VFX noun for a take
(overriding "Generation"), (b) **Submit** collides with the VFX status "submit to client", and
(c) the single-number problem above was unresolved.

## Decision

**Acts (verbs).**
- **Submit** — send a **Run** to a model/farm (API / Comfy / Flamenco). The Submitter does this.
  "Cast" is dropped (flavor).
- **Publish** — promote a Version across the **internal** review gate.
- **Deliver** — promote a Publish across the **client** gate. ("Submit to client" → use *Deliver*.)

**Artifacts (nouns) and their gated namespaces — numbers RESET at each gate:**

| Artifact | Produced by | Numbering (per Shot) | Audience |
|---|---|---|---|
| **Run** | a Submit | — (a logged event; has a `type`) | internal |
| **Version** | a Run | `v001…` (work takes) | internal |
| **Publish** | promoting a Version | `p001…` (own namespace) | supervisor |
| **Delivery** | delivering a Publish | client `v1…` (own namespace) | client |

- **Run** — one Submit event against a Shot; records the recipe (flat params + Asset→Role bindings),
  request-id, cost; produces **one or more Versions**. `type` ∈ {`seed-sweep`, `prompt-variation`,
  `xy-plot`, `refine`, …}. Also logs non-gen-AI Skill runs.
- **Version** (replaces **Generation**) — a take; ephemeral address; carries its full recipe.
- **Publish** — a promoted Version; stable, downstream-safe; **thin** (identity + pointer back, recipe
  never duplicated); its own `p###` counter; re-promoting after a note makes the next Publish.
- **Delivery** — a Publish promoted across the client gate; a **special kind of Publish** with a
  **client-facing counter that resets**, so the client's first sight is **v1** regardless of internal
  churn.

**Provenance is carried by lineage, not numbers.**
- **Lineage** = the pointer chain **Delivery → Publish → Version → Run** (and **Asset → Publish/Import**).
  Each gate numbers independently; "what were the earlier takes?" is answered by walking pointers.
- **Downstream may reference only Publishes/Deliveries**, never a Version's ephemeral address.

**Inputs unify with this model (from the asset-versioning grill).**
- An **Asset** is a versioned input bound into a Shot in a **Role**; its content is a **Publish**
  (internal output re-entering) or an **Import** (external file). The system resolves the Asset's
  **promoted** version (current Publish/Import) when writing prompts and wiring workflows.
- **Role** lives on the **binding** (Asset × Version usage), not the Asset, and is the wiring key
  (prompt reference + Comfy node / API slot). Recorded as `{asset → pinned Publish/Import, role}`.
- **Import** is the external sibling of a Publish (no source Version); the distinction keeps
  provenance honest.

## Consequences
- The DB/Manifest schema (next branch) is shaped by this: a `runs → versions → publishes → deliveries`
  spine with **pointer** edges, plus the recipe (flat) vs lineage (edges) split from handoff §6.
- On disk: `<Shot>/versions/{render,upscale,comp}/` + `<Shot>/publishes/`; Deliveries are records that
  assemble into the Episode `deliverables/` package (see ADR 0003).
- "Generation" and "Cast" leave the active vocabulary (`_Avoid_`); this extends ADR 0004's divergence
  from the prior "LOCKED" UL — recorded so no one reverts it.

## Why an ADR
This is the backbone of provenance for the entire pipeline; the DB, Submitter, prompt-writing, and
client deliveries all depend on the gated-namespace + lineage rule. It is hard to reverse (re-keying
every artifact) and surprising to a VFX reader who expects one carried version number — exactly the
assumption it deliberately rejects.
