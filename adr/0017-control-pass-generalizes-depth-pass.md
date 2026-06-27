# ADR 0017 — `control-pass` generalizes `depth-pass`: control/structure inputs are one run.type, flavored by Spell

**Status:** Accepted
**Date:** 2026-06-26
**Amends:** ADR 0014 (the `run.type` dispatch enum), ADR 0016 (the per-run-type `spec` contract)
**Relates:** ADR 0001/0009 (Spell↔Skill, Spellbook), ADR 0012 (Roustabout dispatch)

## Context
ADR 0014 pinned **`depth-pass`** as a dedicated `run.type`; ADR 0016 gave it the spec
`{method:<variant spell>, params:{…}}`. Hardening the model exposed that depth is **not unique**:
**canny, openpose, mattes** are the *same operation* — derive a control/structure reference from a
Source plate/frame and bind it into a downstream gen. Minting a `run.type` per control kind
(`canny-pass`, `openpose-pass`, …) would bloat the single dispatch enum (ADR 0014) and duplicate **one
flow** N times in the Roustabout's `FLOWS` table.

The flavor already lives in the right place: `spec.method` **names a Spell** (`depthcrafter-bw20`,
`depthcrafter-anyline-combo`). So the type token `depth-pass` was over-specific — the variation it implied
was already carried by the Spell, not the type. Depth was special only by accident of being the first
hardened control craft.

## Decision
Replace `depth-pass` in the `run.type` enum with one generic **`control-pass`**.

- A **`control-pass`** derives a **control/structure reference** (depth, canny, openpose, matte, …) from a
  **Source** plate/frame and produces a **Publish** bound downstream in a **per-kind Role**.
- The **flavor is a Spell**, selected by **`spec.method`** — e.g. `depthcrafter-bw20`,
  `depthcrafter-anyline-combo` (depth flavors), `canny`, `openpose`, `matte-*`. **One run.type, many
  Spells.** Spec shape is unchanged from 0016: `{method:<spell>, params:{…}}`, expanding to **1 → a control
  Publish**. The substantive "what it does" (the ComfyUI graph, ffmpeg comp, opacity) stays in the **Spell**
  in `spellbook/spells/` — the run.type + spec are only the typed handle that names and parameterizes it.
- **Role stays per-kind** (`Depth-Pass`, `Canny`, `OpenPose`, `Matte`). Role is the **wiring key** — which
  Comfy node / API slot the control feeds (CONTEXT *Reference / Role*) — so it must name the **specific**
  control, while `run.type` names the **family** for dispatch. The two key on different axes on purpose.
- **Scope is control/structure maps only.** **Audio** prep and **creative assets** (Character-Sheet,
  First/Last-Frame, Lipsync-Dialog) are **out** — they dispatch and expand differently and keep their own
  handling (ADR 0015 cut, confirmed Session 7).
- The hardened **`depth-pass` Skill stays** — it now reads as the **depth family of `control-pass`
  methods**. A depth Run logs `type: control-pass`, `spec.method: depthcrafter-…`.

Rejected: a `run.type` per control kind (enum bloat, N-duplicated flow); a `mode`/sub-key split on a generic
type (more dispatch code, fights the existing single-key `FLOWS[run.type]` — same reasoning that rejected
Model B in ADR 0014); folding creative assets in too (they aren't preprocessor-shaped — ADR 0017 scope cut).

## Consequences
- **ADR 0014 enum** becomes `{seed-sweep, prompt-variation, xy-plot, refine, comp, upscale, control-pass}`
  (`depth-pass` → `control-pass`). Single-key dispatch preserved; the Roustabout **sub-branches on
  Role / `spec.method`** *inside* the one `control-pass` flow (consistent with 0012/0014 "branches by
  run.type / Role / stage").
- **ADR 0016 spec table** row `depth-pass` → `control-pass`: same `{method, params}` shape, now covering all
  control kinds. The Submitter validates `method` is a known Spell and (where the Spell declares knobs) its
  params.
- **New Roles** (`Canny`, `OpenPose`, `Matte`) join the open `bindings.role` vocabulary — **no schema
  change** (`runs.type` is open text; `runs.spec` already exists per 0016).
- **Data:** existing `depth-pass` `runs.type` rows re-tag to `control-pass` with `spec.method` set
  (one-time; trivially few today, mostly legacy).
- The `FLOWS[run.type]` table (Roustabout grill, HANDOFF §OPEN 5) keys on the **seven** values above; the
  `control-pass` entry is one flow that fans out by Role/method.

## Why an ADR
It changes the **dispatch enum the Roustabout is built against** and the **spec contract the Submitter
validates** — the two seams ADRs 0014 and 0016 exist to pin. Reversing it means re-tagging stored runs and
re-cutting the `FLOWS` table, so the generalization (and its scope cut) is on record.
