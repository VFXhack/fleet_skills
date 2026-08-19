# ADR 0028 — Watts is the project store; Huxley is compute

**Status:** Accepted
**Date:** 2026-08-19 (Session R2; ruled R-1, 2026-08-18)
**Amends:** ADR 0002 (store placement reversed; platform-neutral `base_path` unchanged)

## Context
ADR 0002 placed the canonical project store on huxley's big storage, and `create-project`
proved it works (`\\huxley\io_common\projects\TEST\SANDBOX`, Session 9). But all six weeks
of real production ran from watts `D:\Projects\WBTV\AWA\…` (plus the leary mesh library),
with huxley used as **compute** (ComfyUI :9110, diffusers) whose outputs land in
`io_common/output/` and get copied back to watts by hand. The "one authoritative copy on
huxley" never existed in practice; meanwhile huxley's root disk is under pressure (238 GB
stray HF cache) and its nvme is fully occupied by ComfyUI. Reality voted with its feet.

## Decision
- **Canonical project trees live on watts** — `D:\Projects` now, `E:` for bulk — served
  to the fleet as the authoritative copy. Leary remains a clone/consumer, never a second
  head.
- **Huxley's nvme is compute-local scratch**, not a store: render inputs are staged to
  it, outputs land in it, and **keepers get pulled back to the watts tree and registered**
  (Version address in the `fleet` DB). Anything left on huxley scratch is presumed
  disposable.
- ADR 0002's **platform-neutral `base_path`** mechanism survives unchanged: the Manifest
  stores a logical root + slug, resolved per-machine. Only the physical home moves.

## Consequences
- The proving lane (brief §4, R-2) runs in a real ADR-0003 tree on watts with real shot
  codes; existing `zombo_v002` artifacts stay in place and are referenced/backfilled.
- The pull-back-and-register step becomes an explicit spine responsibility (the Submitter
  writes the Version address only after the artifact lands in the watts tree — ADR 0013).
- Watts inherits the "authoritative copy" burden: its project volumes join mckenna in
  needing a backup story (tracked, not solved here).
- Huxley scratch hygiene (HF cache to `/nvme1/comfyui/hf_cache`, periodic sweep of
  `io_common/output/`) is ops, not architecture.

## Why an ADR
It reverses ADR 0002's central placement decision — the load-bearing "where do projects
physically live" fact that the Manifest, Submitter, and every file-touching Skill build
against — and records that the reversal came from six weeks of production evidence, not
preference.
