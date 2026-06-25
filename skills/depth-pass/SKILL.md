---
name: depth-pass
description: >
  Generate a depth/structure reference *video* from a shot's locked plate (its 720
  Hero or source clip) to guide a gen-AI video pass. Use whenever the user says
  "make a depth pass", "depth map for this shot", "need a depth reference", or before
  a 1080 sweep that needs depth/structure conditioning. This is the hardened SPINE of
  the depth-pass craft; the specific tool recipe is a swappable variant Spell.
---

# depth-pass

> **Status:** v0.2 — realigned to ADRs 0003/0005/0008 (2026-06-25). Encodes the common
> **spine** only; the concrete depth recipe is a **variant Spell** (see *Variants*). Variant
> internals (exact params, ffmpeg comp, Anyline settings) get pinned when the Spells migrate
> from Notion / the project `CLAUDE.md` recipes into `spellbook/spells/` (ADR 0009).

## When to use
You have a Shot's **locked plate** — typically its **720 Hero** (the tagged, motion-locked
winning render) or a source clip — and you need a **depth/structure reference video** to condition
a downstream gen-AI video pass (e.g. the 1080 sweep, where it wires in as the `@Video1` motion guide).

## Inputs
- `source` — the input clip: the Shot's **720 Hero Publish** (preferred) or a source plate. A
  **Publish** or **Import**, resolved to its promoted file.
- `shot` — the Shot this belongs to (`JOB_SEQUENCE_SHOT`, e.g. `AWA_SALEM_010`), so the output
  **Publish** and the **Run** log route correctly.
- `variant` — which depth recipe to run (a Spell; see *Variants*). Default = the most-invoked.
- `params` — variant-specific knobs (the Spell owns these — e.g. DepthCrafter steps/guidance/window,
  output res/fps, B&W comp opacity). Not part of the spine.

## The spine (what's hardened)
Regardless of variant, every depth pass:
1. Takes a **locked plate** (the 720 Hero) as input.
2. Runs a **ComfyUI graph on Huxley** (via comfy-runner) to produce a **depth/structure reference
   video** (temporal — over the whole clip; 24fps to reduce frame-to-frame jumping).
3. Emits the result as a **depth Publish** (`p###`) in `<Shot>/publishes/`, never an ephemeral Version
   — because downstream (the 1080 sweep) **references only Publishes**.
4. Is logged as a **Run** of type `depth-pass` to the Postgres provenance store (ADR 0008), via the
   **Submitter** — a non-gen-AI Skill execution that produces a Publish (per CONTEXT *Run*).

## Variants (Spells — not hardened here)
The concrete recipe is a swappable Spell. Known live variants (canonical recipes currently in the
project `CLAUDE.md` files / Notion, pending migration to `spellbook/spells/`):
- **`depthcrafter-anyline-combo`** — **DepthCrafter (FG depth) + Anyline (BG line-art)** → combined
  depth/line mp4. The documented "Current Best Practice" (Centenario `CLAUDE.md`); better BG structure
  than pure depth.
- **`depthcrafter-bw20`** — DepthCrafter depth → ffmpeg B&W of the orig → comp depth over B&W at
  **20% opacity** → `*_depthXbw20_*`. Most recent CTO usage.
- **`seedance-color2depth`** — *deprecated*: caused face-identity bleed; do not use.

## Steps
1. Resolve `source` (the 720 Hero Publish / plate) and the target `shot`.
2. Select the `variant` Spell (default = most-invoked) and its `params`.
3. Run the variant's ComfyUI graph **on Huxley** to produce the depth/structure reference video.
4. Promote the result to a **depth Publish** (`p###`) in `<Shot>/publishes/`, with a pointer back to
   its source plate.
5. Log the **Run** (`type: depth-pass`, inputs, variant, params, output Publish) to **Postgres via the
   Submitter**; the Submitter emits `VersionRecorded` for Griptape to pick up (proxy etc.).
6. Return the depth **Publish** pointer (`p###`).

## Outputs
- A **depth Publish** (`p###`) — a depth/structure reference video in `<Shot>/publishes/`.
- A logged `depth-pass` **Run** in the Postgres provenance store.
- Downstream, that Publish re-enters the next Shot/sweep as an **Asset** in the **Depth-Pass Role**.

## Notes
- Downstream of **`create-project`** (needs the ADR-0003 Shot tree to write into) and typically of a
  locked **720 Hero** Publish.
- **Variants stay as Spells** in the Spellbook (ADR 0001 / ADR 0009); this Skill hardens only the common
  spine and exposes the most-invoked path. Pin variant params when each Spell is migrated.
- Runs in **ComfyUI on Huxley** (the renderer) via comfy-runner; not a local/CLI step.
- **Provenance is in Postgres, not the Manifest** (ADR 0006/0008) — never log the Run to the Manifest.
