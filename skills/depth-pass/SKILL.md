---
name: depth-pass
description: >
  Generate a detailed depth-pass reference from a plate or frame, to guide gen-AI
  video. Use whenever the user says "make a depth pass", "depth map for this",
  "need a depth reference", or before a gen step that needs depth conditioning.
  This is the hardened version of the depth-pass Spell from the Spellbook.
---

# depth-pass

> **Status:** Draft template (v0.1). Port the real method from the Spellbook (ex-cookbook)
> entry during Session 3. The TODOs below mark where your actual workflow goes.

## When to use
You have a plate/frame and need a depth-map reference to condition a gen-AI video pass.

## Inputs
- `source` — path to the input image/frame (typically from a Project's `00_input/`).
- `project` — the Project this belongs to (so output + logging route correctly).
- `params` — depth-method settings (TODO: list your real knobs, e.g. model, resolution,
  near/far clamp, blur, normalization).

## Method (TODO — port from Spellbook)
1. <TODO: the depth model / tool you use and how you invoke it>
2. <TODO: pre-processing of the plate>
3. <TODO: depth generation step + the settings that make yours "detailed">
4. <TODO: post-processing — normalization, clamping, format>

## Steps
1. Resolve `source` and the target `project`.
2. Run the method above to produce the depth pass.
3. Write output to `<project>/01_depth/` with a versioned, descriptive filename.
4. Log the Run (inputs, params, output path) to `<project>/logs/` and the Manifest —
   via the Submitter so it lands in Mckenna's DB.
5. Return the output path.

## Outputs
- A depth-pass file in `01_depth/`.
- A logged Run in the Manifest + Mckenna DB.

## Notes
- This Skill is downstream of `create-project` (needs a Project to write into).
- If the method grows multiple variants, keep the variants as Spells in the Spellbook
  and let this Skill expose the common, most-invoked path.
