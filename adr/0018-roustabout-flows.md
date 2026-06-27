# ADR 0018 — Roustabout FLOWS: two-tier reactions, bounded auto-publish, wired chains, and the `PublishRecorded` event

**Status:** Accepted
**Date:** 2026-06-26
**Refines:** ADR 0012 (Roustabout role), 0013 (Submitter writes `address`, emits `VersionRecorded`),
0014 (`run.type` dispatch), 0016 (`spec` expands to N versions), 0017 (`control-pass`)
**Paired with:** ADR 0019 (event delivery mechanism)

## Context
ADR 0012 fixed the **Roustabout** as the deterministic floor that reacts to `VersionRecorded` and
"branches by `run.type` / Role / stage", running a pre-wired flow (proxy, log, notify, chain). HANDOFF
§OPEN 5 left the actual `FLOWS[run.type]` undefined: what fires per type, whether it may **cross a gate**
(auto-publish), whether it may **start new work** (chaining), and what events it even hears. Two doc
contradictions needed resolving: the `depth-pass` Skill "emits a **Publish** … never a Version" vs View 1b
"assets are **supervisor-approved**"; and "chain next stage" vs "**no judgment**".

## Decision
1. **Two tiers of reaction.** The Roustabout fires **per-take** actions on each `VersionRecorded`, and
   **per-run** actions at a **completion barrier** — "N of N versions of this run have landed." N is the
   count the Submitter expanded the `spec` into (ADR 0016), so the barrier is a **deterministic, countable
   fact the Roustabout reads**, never a judgment.
2. **Skeleton (type-independent policies, not 7 bespoke rows).**
   - **Per-take:** render **proxy/thumbnail** + write a **structured log** entry.
   - **Per-run (barrier):** assemble a **contact sheet** when the run produced **>1 comparable take**; fire
     **one** "run complete" notify (not N); **auto-publish** per rule (3).
3. **Bounded auto-publish.** The Roustabout may cross **Version→Publish** only when
   `run.type ∈ {control-pass, upscale, comp}` **AND** the run expanded to **exactly 1 version**. The
   creative sweep-shapes (`seed-sweep`, `prompt-variation`, `xy-plot`, `refine`) **never** auto-publish —
   choosing among takes is judgment (human / Ringmaster). This resolves the contradiction: **`control-pass`
   is the deliberate exception** — 1 deterministic output, nothing to choose. The output **lands as a
   Version, then is auto-promoted** (keeping the event model uniform — this corrects the Skill's "never a
   Version" wording). **Reconciliation with View 1:** the internal "promote" gate on `comp` / up-res becomes
   **automatic for single-output runs**; the human check moves to the checkpoint already downstream — **QC
   on the up-res Publish**, the **client gate** for a comp, the **downstream-gen review** for an
   auto-published asset. (A pre-publish glance traded for a post-publish one — accepted.)
4. **Wired chains (the Roustabout may start new Runs) — judgment-free only.** A chain is a
   `(trigger + match) → fully-pinned Run recipe`: method = the **pinned default Spell**, params fixed,
   source = the trigger artifact. The moment a transition needs **any runtime choice** (which take, which of
   several methods, "is it good enough"), it is **not eligible** as a chain and goes to a human / the
   Ringmaster. The chain **registry is a short, explicit list**, never a general workflow graph; when a
   chain's default stops being obvious, that is the signal it **graduates up to the Ringmaster**.
5. **Second event: `PublishRecorded`.** Chains fire on **Publishes** (e.g. a tagged 720 Hero → its depth
   `control-pass`), and a Publish is born **either** by the Roustabout's auto-publish (3) **or** a human
   supervisor-gate promote. So the **Submitter emits `PublishRecorded` on every publish insert** (uniform
   with `VersionRecorded` — the Submitter is the sole writer/emitter). The Roustabout listens to **both**:
   `VersionRecorded` → tiers 1–2; `PublishRecorded` → chains, **matched on the Publish's Role/tag**.

(How both events are *delivered* is ADR 0019.)

## Consequences
- Roustabout dispatch now has **two keys**: `FLOWS[run.type]` on `VersionRecorded` (reactions) and a
  **`CHAINS`** list on `PublishRecorded` keyed by **Role/tag** (follow-on Runs).
- The Roustabout **reads the run's expected version count** (Submitter expanded `spec` → N, ADR 0016) to
  evaluate both the barrier and the auto-publish `== 1` test — a **read**, not orchestration-in-DB.
- **View 1 / View 1b** shift: single-output `comp`/up-res internal gate is automatic; `control-pass` lands a
  Version then auto-publishes. PIPELINE updated to match.
- A **new `PublishRecorded` event** joins `VersionRecorded`; the Submitter emits both.
- Auto-publish and chains **must be idempotent** (ADR 0019's outbox is at-least-once).
- The **notify target/channel** (Notion view / a feed) is a deferred config detail — not load-bearing here.

## Why an ADR
It defines the Roustabout's **authority** — which gates it may cross, what work it may start — and **adds an
event to the system seam**: the exact line between the deterministic floor and the judgment floor. Reversing
it means re-drawing that boundary and removing an event the Submitter emits.
