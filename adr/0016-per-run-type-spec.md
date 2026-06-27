# ADR 0016 — Per-run-type spec: each `run.type` declares the variables it needs; the Submitter expands it

**Status:** Accepted — *`depth-pass` row generalized to `control-pass` by ADR 0017*
**Date:** 2026-06-26
**Builds on:** ADR 0005 (run types), 0007 (authoring vs resolved recipe), 0011 (schema), 0014 (run.type enum)
**Amended by:** ADR 0017 — the `depth-pass` spec row below generalizes to **`control-pass`**: same
`{method:<variant spell>, params}` shape, now covering depth/canny/openpose/matte (flavor = the Spell).

## Context
ADR 0014 fixed `run.type` as the single dispatch enum, but nothing defined *what variables each type
actually requires*. A `seed-sweep` needs a seed list; an `xy-plot` needs two axes (what's plotted and the
values); an `upscale` needs a source + model + factor. Without a per-type contract the Submitter can't
validate a Run, the Roustabout can't know what a Run will produce, and an `xy-plot` like "LoRA strength
0.2–0.8 ×2 vs CFG 3–4 ×4" has nowhere well-defined to live.

The existing schema already had `runs.params jsonb` (flat params) and `versions.delta jsonb` (the swept
value per take), but no place for the *variation/operation definition* itself.

## Decision
A Run's authoring recipe (ADR 0007) is **`type` + `bindings` + `params` + `spec`**:
- **`bindings`** — *all* inputs, each in a **Role** (existing table). Creative assets (Character-Sheet,
  Plate, …), comp inputs (role `Comp-Input`), and the prior artifact an op consumes (role `Source`) are
  all bindings. Because a bare Version can't be bound (ADR 0005), `refine`/`upscale`/etc. **source a
  Publish**.
- **`params`** — the fixed base knobs held constant across the Run.
- **`spec`** — a **type-specific** object describing *what varies / how the op runs*. Stored in a new
  `runs.spec jsonb` column (migration 0002), kept separate from `params`.

The **Submitter validates** `spec` knob names against the **Template's declared knobs** (the Template owns
each knob's key→Comfy-node/API-slot mapping, mirroring how `role` maps an asset to a slot), then
**expands** `spec` into N Versions, each carrying its resolved **`delta`** + frozen submission.

**Per-type `spec` contract:**

| type | bindings (role) | spec | expands to |
|---|---|---|---|
| seed-sweep | creative assets | `{seeds:[…]}` (sugar `{base,count}` / `{random,count}`) | N · `{seed}` |
| prompt-variation | creative assets | `{knob, variants:[{label,value}…]}` | N · `{knob}` |
| xy-plot | creative assets | `{x:{knob,values:[…]}, y:{knob,values:[…]}}` | \|x\|·\|y\| grid |
| refine | creative assets + Source=Publish | `{changes:{knob:val,…}}` | 1–N |
| comp | Comp-Input(s)=Publish/Import | `{script:<.nk ref in work/nuke/>}` | 1–N |
| upscale | Source=Publish | `{model, params:{factor,…}}` | 1–N |
| control-pass | Source=Publish/Import (plate/frame) | `{method:<variant spell>, params:{…}}` | 1 → control Publish (depth/canny/openpose/matte; bound in a per-kind Role) — ADR 0017 |

**Conventions:**
- **Sweep `values` are stored EXPLICIT.** `{from,to,steps,scale}` is *input sugar* the Submitter expands
  at submit time; the Run records the resolved value list, so a grid is reproducible forever and never
  depends on re-deriving from a range.
- **`steps` counts DATA POINTS** (inclusive endpoints): `0.2–0.8 ×2 = [0.2, 0.8]`; `3–4 ×4 =
  [3.0, 3.33, 3.67, 4.0]`; the worked example is a **2×4 = 8-version** grid.
- **`seed` is a reserved knob.** `xy-plot` generalizes the one-axis sweeps (seed-sweep is the degenerate
  `x=seed` case); the types stay distinct for clean Roustabout dispatch (ADR 0014).
- **Knob addressing is a flat param key** the Template exposes (`cfg`, `lora.character.strength`,
  `seed`) — not a raw Comfy-graph path.

## Consequences
- **Schema:** migration 0002 adds `runs.spec jsonb NOT NULL DEFAULT '{}'`. No CHECK — validation is the
  Submitter's job against the Template, not the DB (ADR 0008).
- **Two new Roles** (`Source`, `Comp-Input`) join the open `bindings.role` vocabulary; no schema change.
- The Submitter gains a per-type **expander** (spec → versions). The Roustabout's `FLOWS[run.type]` (next
  grill) can rely on a typed, validated spec and a known version count.
- Reproducibility (ADR 0007) extends to sweeps: the explicit value list + per-version frozen submission
  reproduce any cell without re-deriving the grid.

## Why an ADR
The per-type contract is what the Submitter validates, the expander reads, and the Roustabout dispatches
on; it pins the sweep grammar (explicit values, points-not-intervals, param-key addressing,
inputs-via-bindings) every gen tool depends on. Changing it later means re-specifying every run type and
re-keying stored specs.
