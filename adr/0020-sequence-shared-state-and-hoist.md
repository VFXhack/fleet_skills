# ADR 0020 — Sequence shared state, the Sequence Pattern, and Hoist

**Status:** Accepted
**Date:** 2026-06-28
**Amended by:** ADR 0021 — the **Sequence Pattern** is renamed **the Sequence Look** (and the rename is
carried into the DB: `sequence_look_runs` / `sequence_look_bindings` / `sequences.look_version` /
`produced_by_look_run_id`). A **prototype Run** is a **Look Run**; a **pattern binding** is a **Look
input**; *instantiate* a Shot is **Cast** a Shot from the Look. The shape of the model is unchanged — only
the names. The terms below are the superseded first-draft vocabulary; read them through ADR 0021's map.
**Amends:** ADR 0003 (assets were *two-tier*; no Sequence level) and ADR 0008 / ADR 0011 (Episode/
Sequence/Shot structure kept *out* of the DB — "Shot is a TEXT CODE, not a table"). This ADR carves a
deliberate, narrow exception for **Sequence configuration** and introduces the **Sequence Pattern**.
**Relates:** ADR 0007 (authoring vs frozen recipe), ADR 0013 (immutable takes), ADR 0016 (`runs.spec`),
ADR 0017 (control-pass generalizes depth-pass).

## Context
A **Sequence** (e.g. `SALEM`) is a group of Shots that share production attributes. Until now Sequence
was only a folder name and a path token — it carried no state. Two needs drove the change:

1. **Downward sharing** — set an attribute once on the Sequence; every Shot uses it; change it once and
   they all follow.
2. **Upward propagation** — develop a client-requested change on **one** Shot, approve it there, then push
   it **up** so the rest of the Sequence adopts it and re-runs.

The real workflow (Andy, as VFX supervisor) is **look-dev driven**: you pick one Shot as the **target**,
develop the whole look on it (e.g. SALEM shot 3 in LTX — find the character sheet, the depth-pass flavor,
the LUT weights, the CFGs), approve it, then **push that pattern up to the Sequence** so the other four
Shots are built the same way. But pushing is **not** all-or-nothing: in that shot, the **character sheet**
and **LUT/CFG/workflow settings** must propagate to every Shot, while the **audio** changes per Shot and
the **depth pass** must be **regenerated per Shot** (its settings shared, its content not).

That exposes a **three-way taxonomy** every Shot input falls into — the rule that decides what propagates:

| Class | Meaning | Example | Home |
|---|---|---|---|
| **shared-content** | one artifact, every Shot uses it | character sheet | `assets.scope='sequence'` |
| **shared-recipe** | same settings, each Shot **regenerates its own content** | depth-pass @ 20% B&W | a prototype Run in the Pattern |
| **per-shot** | different input each Shot, no sharing | audio | `assets.scope='shot'` |

Shared *params* (LUT weights, CFG, model/tier/mode) behave like shared-content (one value, inherited) with
per-Shot override.

Also: **promote** is reserved for the **gate** verb (Version→Publish→Delivery; ADR 0005). The upward push
is not a gate crossing and must not reuse it.

## Decision

### 1. The sharing taxonomy is first-class
Every Role (and param) carried by a Sequence is classified **shared-content | shared-recipe | per-shot**
(table above). This classification is the mechanism that drives both selective **Hoist** (what goes up)
and **instantiation** (what each Shot inherits vs must supply itself).

### 2. Sequence becomes a first-class **config** record (not a structure authority)
Add a `sequences` table holding settings only:

```
sequences (
  id               uuid pk,
  project_id       uuid -> projects(id),
  sequence_code    text,                 -- e.g. 'AWA_EP01_SALEM'
  title            text,
  lookdev_shot_code text,                -- the designated target Shot (§5); nullable
  pattern_version  integer default 0,    -- bumped by each Hoist (§7)
  UNIQUE (project_id, sequence_code)
)
```

A Sequence's **existence** is still its **folder** (ADR 0003), walked as before. The DB stores its
*settings*, never the authority on which Sequences exist. This is the **one** place "structure is never
in the DB" is relaxed, and only for *config*.

### 3. The **Sequence Pattern** — a set of prototype Runs (shape B)
A **Sequence Pattern** is the master recipe pattern every Shot in the Sequence is built to: a **set of
prototype Runs** (the LTX **render** Run, the **depth-pass**/control-pass Run, etc.) mirroring a Run's
authoring recipe (`type`, `template_ref`, `model`, `tier`, `mode`, `params`, `stage`) **minus per-Shot
content**, each with a per-Role/param **sharing class**. Sketch:

```
sequence_pattern_runs (
  id           uuid pk,
  sequence_id  uuid -> sequences(id),
  type         text,        -- render | control-pass | upscale | ...  (ADR 0014)
  stage        text,        -- render | upscale | comp  (ADR 0003)
  template_ref text, model text, tier text, mode text,
  params       jsonb,       -- shared authoring params (LUT, CFG, workflow settings)
  ord          integer      -- order in the per-Shot chain
)
sequence_pattern_bindings (
  id              uuid pk,
  pattern_run_id  uuid -> sequence_pattern_runs(id),
  role            text,                          -- 'Character-Sheet' | 'Depth-Pass' | 'Lipsync-Dialog' | ...
  sharing_class   text CHECK (sharing_class IN ('shared-content','shared-recipe','per-shot')),
  -- a binding is sourced exactly ONE of three ways, matching its class:
  asset_id                   uuid -> assets(id),                 -- shared-content: a Sequence-scoped Asset
  produced_by_pattern_run_id uuid -> sequence_pattern_runs(id)   -- shared-recipe: another prototype Run, re-run per Shot
  -- per-shot: both NULL (the Shot supplies its own). CHECK enforces source==class.
)
```

It mirrors the existing `runs`/`bindings` shapes deliberately, so **Hoist = lift recipe up** and
**instantiate = clone recipe down** are the same copy in two directions.

A **shared-recipe** Run is **not special machinery** — it is an ordinary Run *type* (the depth-pass is
just a `control-pass`, ADR 0017), and its per-Shot output is **auto-published no-look by the Roustabout**
(ADR 0018). The Pattern adds nothing to how that Run executes or publishes; it only records that the
Sequence **re-runs this type per Shot**, and (Open, §below) which Run's output feeds which consuming Role.

### 4. Shared **assets** get a Sequence **binding scope** (no new folder)
Extend `assets.scope` to **`('job','sequence','shot')`** + nullable `sequence_code` (required iff
`scope='sequence'`). A Sequence-scoped Asset's **file still lives flat in `<Job>/assets/`** — there is no
Sequence asset folder; `scope='sequence'` is a *binding scope* ("auto-bind to every Shot in this
Sequence"), consistent with "scope/Role is metadata, not folders." This is the home for **shared-content**.

### 5. The **look-dev (Target) Shot**
A Sequence may designate one Shot (`sequences.lookdev_shot_code`) as its **target**: the Shot where the
look is developed and iterated. It is an ordinary Shot — it just also serves as the source the Pattern is
Hoisted **from**. Designation is a human (supervisor) choice; a Sequence has at most one at a time.

### 6. **Hoist** — selective, driven by the sharing class
**Hoist** lifts the **approved** look-dev Shot's recipe **up** into the Sequence Pattern:
- The sharing class is **born here** (decided at Hoist, not at authoring): the supervisor **classifies**
  each Role/param (shared-content | shared-recipe | per-shot) once the look-dev look is approved. The
  classification persists on the Pattern (`sequence_pattern_bindings.sharing_class`) and is editable on
  re-hoist. Authoring a look-dev Run stays untagged/clean; Hoist is the single deliberate gate.
- **shared-content** Roles → the bound Asset is lifted to a `scope='sequence'` Asset (`asset_id`).
- **shared-recipe** Roles → the producing Run's recipe is lifted into a prototype Run, and the consuming
  Role records `produced_by_pattern_run_id` → that Run; **content is not** lifted (re-run per Shot, then
  Roustabout no-look auto-publishes and binds it — ADR 0018).
- **per-shot** Roles → **not** hoisted (each Shot owns its own).
- Shared **params** are lifted into the relevant prototype Run's `params`.
- The look-dev Shot's now-redundant overrides for the **hoisted** attributes are **cleared** (it returns
  to inheriting them from the Pattern); its per-shot attributes stay local.
- `pattern_version` is bumped.

Hoist **never rewrites existing takes** — provenance is immutable (ADR 0013); siblings **re-run forward**.
Hoist moves a value **up the structure** (Shot→Sequence); it is **not** *promote* (a take across a gate).

### 7. **Instantiate** — a non-target Shot builds itself from the Pattern
When a non-target Shot submits its **next** Run, the Submitter materializes the Pattern for that Shot:
- clone each prototype Run into an actual `runs` row for the Shot;
- **shared-content** → bind the Sequence-scoped Asset automatically;
- **shared-recipe** → schedule that recipe to **run for this Shot** (e.g. generate this Shot's own depth
  pass at the shared 20% B&W settings);
- **per-shot** → **require** the Shot to supply its own input (flag a missing audio, etc.);
- apply shared params, with any **Shot override winning** (ADR 0020 §Override);
- freeze the resolved submission per Version (ADR 0007) and record the `pattern_version` it was built
  from, so a take's lineage answers "which Pattern version made this?"

### 8. **Override** — a Shot's local value, which also shields it
A Shot may override any inherited (shared-content / shared-recipe / param) value. An override means the
Shot uses its own value **and** stops following later Sequence-wide changes to that attribute (value **and**
shield). A Hoist does not disturb a sibling that holds its own override of the hoisted attribute.

## Consequences
- The "open one folder, see everything" ethos holds: no new folders; sharing is DB metadata, like Role.
- A take's frozen submission captures exactly what it inherited (content, recipe, params) **at submit** —
  no later Pattern edit can retro-change history; siblings re-run forward.
- The Submitter gains two real steps: **resolve inheritance** (Shot over Sequence) and **instantiate the
  Pattern** (clone prototype Runs, schedule shared-recipe Runs, demand per-shot inputs).
- The Sequence Pattern is heavier than a defaults blob — it stores **re-runnable recipe patterns**, which
  is exactly what the depth-pass case requires.
- "Structure is never in the DB" becomes "structure is never in the DB, but a Sequence's **config +
  Pattern** is" — a smaller, explicitly-bounded claim.

## Open (settle when building; not blockers)
- **Where a Shot's overrides live** — likely a `shot_overrides` home mirroring the Pattern, or carried on
  the Shot's authoring at run time. Decide with `add-shot`. **Settled by ADR 0023:** a dedicated
  `shot_overrides` table, one row per overridden attribute, keyed by stable codes (never `look_run_id`).
- **`sequence_code` form** — proposed `JOB_EP_SEQ` (`AWA_EP01_SALEM`), mirroring ADR 0015.
- **Pattern provenance breadcrumb** — optionally record which Shot+take each Pattern value was Hoisted from.
- **Execution ordering of the prototype-Run chain** — `produced_by_pattern_run_id` now gives an explicit
  producer→consumer link (a shared-recipe Role names the Run that feeds it), so the *dependency* is
  captured; what's still open is whether `ord` alone is enough to *schedule* the per-Shot chain (render +
  control-pass + upscale) or the producer links should drive a topological order. Settle when building
  Instantiate.

**Decided since first draft:** the sharing class is **born at Hoist** (not tagged at authoring), and a
binding's source splits three ways (`asset_id` for shared-content, `produced_by_pattern_run_id` for
shared-recipe, neither for per-shot). Depth-pass is **not** special — it is a `control-pass` Run type
auto-published no-look by the Roustabout.

## Why an ADR
It reverses two load-bearing prior decisions (no Sequence level; no structure in the DB), introduces two
new UL concepts (**Sequence Pattern**, **look-dev/Target Shot**) and a new verb (**Hoist**) deliberately
distinct from **promote**, and makes propagation **selective** via a first-class sharing taxonomy. A future
reader will ask "why does a Sequence own prototype Runs when Shots aren't even tables?" — this is the answer.
