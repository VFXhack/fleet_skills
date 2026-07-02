# ADR 0022 — Hoist is publish-driven (anchor on a Publish; latest by default, --publish to override)

**Status:** Accepted
**Date:** 2026-07-01
**Refines:** ADR 0020 §6 (Hoist) / ADR 0021 (the Look). Settles *which* take's recipe a Hoist lifts —
left implicit in 0020. Relates: ADR 0005 (the Publish gate), ADR 0013 (immutable takes).

## Context
Hoist lifts an **approved** look-dev Shot's recipe up into the Sequence Look. ADR 0020 said "approved"
but never said *how the tool picks which take* to lift. The first build guessed **"the latest Run per
type"** on the look-dev Shot — but a look-dev Shot accumulates many iterations (v001..v0NN), and "latest"
is not the same as "approved." Worse, the supervisor routinely needs to change the anchor: look-dev on
`AWA_EP01_SALEM_030` produces v001..v010, `v006` is approved and Hoisted — then client notes come back
matching **v004**. The Look must be re-Hoisted from a *different, specific* take.

The pivot: in this model **approval == a Publish** (ADR 0005). A Publish (`p###`) is a Version that
crossed the internal gate — a durable copy at a stable path plus a row pointing back at its source
Version. A bare Version's file location is ephemeral; only a Publish is safe to build on. So "approved
take" already has a first-class name — the Publish — and Hoist should key on it.

## Decision
**Hoist is publish-driven.** It never lifts a bare Version; it anchors on a **Publish** of the look-dev
Shot:
- **Default** — the **latest** Publish (highest `p###`) on the look-dev Shot. During look-dev the last
  thing you approve *is* the hero, so the default is usually right.
- **Override** — `--publish <n>` anchors on `p<n>` (the client-zigzag case: re-Hoist from an earlier
  approved take).
- From the anchor Publish → its source Version → its **Run**, Hoist walks the recipe graph: the anchor
  Run plus (transitively) the Run producing each **shared-recipe** input (discovered via that input's
  pinned Publish → source Run). Those are exactly the Runs that fed the *approved* take — not the newest
  stray iterations.
- **To Hoist a take that isn't published yet**, `promote` it first. That is not overhead — it is the
  approval being **recorded** as a Publish. The Version keeps its number (no re-render, no renumber); a
  new Publish `p###` simply points at it. Then it is the latest Publish, or you target it with
  `--publish`.

### Rejected: `hoist --version <n>` auto-promote sugar
A `--version` flag that promotes-then-Hoists in one step was considered and **deferred**. It is
convenient but makes Hoist silently perform a **gate crossing** (promote), blurring the two verbs ADR
0020 deliberately kept distinct (Hoist ≠ promote). Not built until the two-step (`promote` then `hoist`)
is felt as real friction — cheap to add later, hard to un-blur.

## Consequences
- The hoisted Look always traces to an **approved, durable** artifact — never a fragile raw take. "Only
  publishes get Hoisted" is enforced by construction (the anchor is a `publishes` row).
- Re-Hoisting to a different take is a one-flag operation (`--publish n`) that rebuilds the Look fresh and
  bumps `look_version`; it never rewrites existing takes.
- Hoist and the Publish gate are **coupled by read** (Hoist reads the gate) but not by write (Hoist does
  not promote). The separation of verbs holds.
- A look-dev Shot with **no** Publish cannot be Hoisted — the tool says so and points at `promote`.

## Why an ADR
A future reader will see Hoist keying on `publishes` and walking source Runs and reasonably ask "why not
just take the latest Run?" — the answer is that *latest ≠ approved*, approval is the Publish gate, and the
supervisor must be able to re-anchor on any earlier approved take. The rejected `--version` sugar is
recorded so the "just let it promote-and-hoist" idea isn't silently re-litigated.
