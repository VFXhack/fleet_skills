# ADR 0004 — Reconciling the prior UL handoff: artifacts, Asset/Role, spine terms

**Status:** Accepted
**Date:** 2026-06-24

## Context
A prior, dedicated UL session (captured in `UL-project-structure-handoff.md` + a "Language Brain
Dump" / "AI Room Doors" diagram) produced a set of decisions marked **LOCKED**. Several collide
with structure decisions made later in this repo's first grill session (ADRs 0002–0003). The
handoff itself flags that the D&D/MTG framing was "a discovery lens, not canon," so its terms were
treated as strong input, not untouchable. Each conflict was grilled and resolved deliberately.

## Decision

**1. Identity spine — keep `Episode` / `Sequence` (reject `Show` / `Scene`).**
Spine = `Client → Project → Episode → Sequence → Shot`. The work is episodic client work, so
*Episode* is unambiguous and *Sequence* is the standard grouping of Shots (and "Scene" carries
narrative ambiguity). `Show`/`Scene` go to `_Avoid_`. **Client** is the top organizing folder but
**not** part of a Shot's identity (an attribute/parent, not a spine coordinate). The concept word
is **Project**; `job_code` is its identifier.

**2. Adopt the Generation / Publish split (the handoff's §5, LOCKED — accepted).**
Shot outputs separate into **Generations** (every ephemeral candidate / seed sweep, full recipe
attached, expiring address) and **Publishes** (a Generation promoted past an approval gate to a
stable, canonical, downstream-safe address — thin, with a pointer back; recipe never duplicated).
**Downstream contexts may reference only Publishes, never a Generation's expiring address.** This
formalizes an instinct already present in the legacy tree (`*_sweep` = Generations,
`*Selects` = Publishes). On disk: `<Shot>/generations/{render,upscale,comp}/` + `<Shot>/publishes/`.

**3. Keep "Asset" for input files; demote "Reference" to a doorway concept; role = metadata.**
The handoff's §7 made **Reference** the canonical word for any AI-room input, keyed by role in
folders. We **diverge**: the canonical word stays **Asset** (an input *file*), stored flat and
descriptively named in two scopes (`<Job>/assets/`, `<Shot>/assets/`). **Reference** is retained as
the *doorway concept* — an Asset entering the AI room in a **Role** (First-Frame Target, style,
plate/driver, …) — but Role is captured as **metadata** on the Generation's recipe / the Run, **not**
as folders. This preserves §7's real value (the Submitter can resolve which Asset is the first frame
for an `i2v` job) while honoring the operator's repeated preference for flat, descriptive,
non-bucketed input files. The brain-dump's other sense of "Asset" (a modeled CG entity) is reserved
and currently unused.

## Consequences
- The provenance model (handoff §6: flat **recipe** attributes travel with the Generation; **lineage**
  is the path + promotion flags) becomes the backbone of the Manifest/DB schema work (next branch).
- Complementary handoff material not in conflict — the canonical **enums** (§10: models, `t2v/i2v/r2v`,
  `api/comfy`, tier, media type), **Submission Prompt / Brief / Target / Mode**, and the
  **Production vs Engineering (Tools)** two-plane split — is adopted as-is and folded in as later
  branches reach it.
- "Reference"/"Role" and "First-Frame Target" remain in the glossary as concepts, not folders.

## Why an ADR
A future reader holding the prior handoff will see decisions stamped **LOCKED** and wonder why the
repo does something else (Asset not Reference; Episode/Sequence not Show/Scene). This records that
the divergence was deliberate and why — and that the Generation/Publish split *was* adopted. Without
it, someone "fixes" the structure back toward a superseded spec.
