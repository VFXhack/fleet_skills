# ADR 0023 — the Override store: `shot_overrides`

**Status:** Accepted
**Date:** 2026-07-02
**Settles:** the ADR 0020 Open item *"where a Shot's overrides live"* (§8 defined what an Override
*means* — a local value **and** a shield — but deferred its home).
**Relates:** ADR 0020/0021 (the Sequence Look, Hoist/Cast, Override semantics), ADR 0022 (Hoist is
publish-driven and **rebuild-fresh** — the fact that forces this table's keying), ADR 0016 (`runs.spec`).

## Context
Cast (the downward half of Hoist/Cast) must **honor Shot Overrides**: when Shot 020 says "my CFG is
4.0, not the Sequence's 3.5", Cast has to apply 4.0, and a later Hoist changing the Sequence value
must **not** drag 020 back — override = value **and** shield (ADR 0020 §8). That demands a persisted
store Cast can read and Hoist can respect. Three candidate homes were on the table (Session 11
handoff):

(a) a dedicated `shot_overrides` table;
(b) a per-Shot config row (`shots` table) with an `overrides` jsonb blob;
(c) no store — stamp the value into the Cast-created Run / frozen submission only.

(c) fails alone: provenance is perfect but the next Hoist/Cast has nothing to consult — value
without shield. (b) works but hides the shape in an unenforceable blob, makes "which Shots override
CFG?" a jsonb path scan, and relaxes "no structure in the DB" a second time with a real `shots` table.

## Decision

### 1. A dedicated `shot_overrides` table — one row per overridden attribute
```
shot_overrides (
  id           uuid pk,
  sequence_id  uuid -> sequences(id) ON DELETE CASCADE,
  shot_code    text NOT NULL,       -- stable identity; Shots remain codes, not rows
  run_type     text NOT NULL,       -- which Look Run it targets (see §2)
  -- exactly ONE of the two forms, enforced by CHECK:
  param_key    text,  param_value jsonb,      -- a param override:  cfg -> 4.0
  role         text,  asset_id uuid -> assets(id),  -- a binding override: Character-Sheet -> my own asset
)
```
- **Param override** (`param_key` + `param_value`): at Cast, merged over the Look Run's `params`
  (override wins).
- **Binding override** (`role` + `asset_id`): at Cast, the Shot's own Asset is bound for that Role
  instead of the inherited source.
- Uniqueness is per attribute: one row per `(sequence_id, shot_code, run_type, param_key)` and one
  per `(sequence_id, shot_code, run_type, role)` — partial unique indexes, since half the key
  columns are NULL on each form.
- Clearing an Override ("start following the Sequence again") = `DELETE` of the row. Listing who
  deviates from the Look = a plain query. CHECKs enforce the two forms; nothing lives in convention.

### 2. Keyed by **stable identity**, never by `look_run_id`
ADR 0022 made Hoist **rebuild-fresh**: every Hoist wipes and re-creates the Look Runs, so their
UUIDs change each time. An Override referencing `look_run_id` would be orphaned (or cascade-deleted)
by the very Hoist it exists to shield against. So an Override addresses its target the same way
`sequences` addresses structure — by **code**: `(sequence_id, shot_code, run_type, param_key|role)`.
`run_type` is the Look Run's stable identity across re-Hoists (the ADR 0014 dispatch key; a Look has
at most one Look Run per type in practice — revisit if that ever breaks).

### 3. Semantics (completing ADR 0020 §6/§7/§8)
- **Cast reads the store**: cloned Run `params` = Look Run `params` ⊕ the Shot's param overrides
  (override wins); an overridden Role binds the Shot's own Asset instead of the inherited source.
  An Override whose `run_type` matches no Look Run is a warning, not an error (typo protection).
- **Hoist clears the look-dev Shot's now-redundant Overrides** (the ADR 0020 §6 clause deferred in
  Session 11): after lifting, the look-dev Shot's overrides for the attributes that were just
  hoisted (matching `run_type` + `param_key` present in the lifted params, or `run_type` + `role`
  present in the lifted bindings) are deleted — that Shot returns to inheriting them. Surgical, not
  blunt: an override on an attribute NOT part of the hoisted recipe survives.
- **Sibling Shots' Overrides are never touched by Hoist** — that is the shield.
- The override *value* still lands in the Cast-created Run's `params` and each Version's frozen
  submission (ADR 0007), so provenance shows what was actually used; the store is the live intent.

### 4. The operator surface is a standalone `override` CLI
`override set | list | clear` — Override is its own UL noun; declaring or clearing one must not
require casting anything. Cast only **reads** the store. (Chosen over `cast --set …` sugar, which
conflates declaring a local value with stamping the Shot and leaves list/clear homeless. Sugar can
be added later without moving the store. — Andy AFK at decision time; recommended option applied,
veto welcome.)

## Consequences
- Cast is buildable: resolve inheritance = Look ⊕ overrides, deterministic and queryable.
- A Hoist can answer "who will NOT follow this change?" before writing (`override list`).
- Two forms in one table means CHECK + two partial unique indexes rather than one UNIQUE — the
  price of row-per-attribute with enforced shape.
- `run_type` as the join key means renaming a run type (ADR 0014 enum change) must migrate
  `shot_overrides.run_type` too.

## Why an ADR
It settles a deliberately-deferred load-bearing question (ADR 0020 Open), the keying choice is
non-obvious (stable codes, forced by ADR 0022's rebuild-fresh — the natural FK would silently
self-destruct), and it fixes the operator surface for a new UL verb pair (override set/clear).
