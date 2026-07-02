# ADR 0021 — Rename the Sequence Pattern to the Sequence Look (down to the DB)

**Status:** Accepted
**Date:** 2026-06-30
**Amends:** ADR 0020 (Sequence shared state, the Sequence Pattern, and Hoist). The **model is unchanged** —
the sharing taxonomy, Hoist, Override, look-dev Shot, and the clone-up/clone-down symmetry all stand. This
ADR changes **only the names**, and carries the rename all the way into the DB.

## Context
ADR 0020 named the shared thing a Sequence carries a **Sequence Pattern**, its prototype Runs **prototype
Runs**, their tagged input slots **pattern bindings**, and the act of a Shot building itself from it
**instantiate**. Building the Hoist engine on top, those words tested as **too abstract for the supervisor's
mental model** (Andy's, the actual user). "Pattern / instantiate" is software vocabulary; it does not name
what is actually happening in the room.

What is actually happening is **look development**: you pick one Shot, develop the whole *look* on it (the
character sheet, the depth-pass flavor, the LUT weights, the CFGs), approve it, and build the rest of the
Sequence to that look. The thing you carry is **the Look**. That word was free (ADR 0020 had rejected
Template/Recipe/Spec/Blueprint as taken/colliding, but never considered Look) and it rhymes with the
already-canon **look-dev Shot** — the place you make it.

## Decision
Rename, with no change to behavior or shape:

| ADR 0020 term (abstract) | ADR 0021 term (the Look) |
|---|---|
| Sequence Pattern / the Pattern | **the Sequence Look** / the Look |
| prototype Run | **Look Run** |
| pattern binding | **Look input** (a Look Run's input slot, tagged by sharing class) |
| *instantiate* a Shot (verb) | **Cast** a Shot from the Look |

**The down-verb is `Cast`.** It pairs with **Hoist** (up) and carries the right mental model: the Look is
the master mold, each Shot is *cast from* it (clone the recipe down). Two near-misses were weighed and
dropped — **Strike** ("strike a print" from a master is apt, but "strike the set" means the *opposite*,
tear-down) and **Conform** (editorial "conform to a reference" is literally accurate but a heavier,
process-y word). "Cast" collides only with actor/role casting, which reads unambiguous in a sentence
("Cast SALEM_020 from the Look"). First draft was the clunky phrase *build a Shot to the Look*; `Cast` is
the single verb that replaced it.

Carry it into the DB (migration `0004`, edited in place — see below):

| Old identifier | New identifier |
|---|---|
| table `sequence_pattern_runs` | `sequence_look_runs` |
| table `sequence_pattern_bindings` | `sequence_look_bindings` |
| `sequence_pattern_bindings.pattern_run_id` | `sequence_look_bindings.look_run_id` |
| `produced_by_pattern_run_id` | `produced_by_look_run_id` |
| `sequences.pattern_version` | `sequences.look_version` |

**Unchanged:** **Hoist**, **Override**, **sharing class** (shared-content / shared-recipe / per-shot),
**look-dev (Target) Shot**, and the table-mirrors-`runs`/`bindings` rationale (now `sequence_look_runs`
mirrors `runs`, `sequence_look_bindings` mirrors `bindings`).

### Depth: the rename goes all the way to the DB
Two options were on the table: rename the UL prose only, or carry it into the table/column names too. We
chose **all the way** for one decisive reason — migration `0004` had been **proven on `fleet_test` but
never applied to prod** (`fleet` was still at `0001`–`0003`). So the change was an **in-place edit of the
unshipped `0004` + re-prove on `fleet_test`** — no prod migration, no data movement. The alternative (UL
says "Look", code says "pattern" forever) is the exact split-vocabulary the domain model exists to prevent;
paying nothing to avoid it was the easy call. The migration file itself was renamed
`0004_sequences_and_pattern.sql` → `0004_sequences_and_look.sql`.

## Consequences
- **CONTEXT.md** (single live truth) now speaks the Look; the old names are listed under `_Avoid_`.
- **ADR 0020** keeps its body as the historical record (its prose still says "Pattern") with an *Amended by:
  ADR 0021* pointer at the top — consistent with how 0020 itself amended 0003/0008/0011 (mark history,
  don't rewrite it).
- The Hoist / Cast engine (the next build) is written on Look-named tables from line one — no later
  rename, no translation tax.
- Had `0004` already shipped to prod, this would have been a genuine migration and the trade-off might have
  tipped to UL-only. It had not, so it didn't.

## Why an ADR
ADR 0020 made a deliberate, reasoned naming choice ("named **Pattern**, NOT Template/Recipe/Spec") and this
ADR reverses it. A future reader hitting the git rename `sequence_pattern_* → sequence_look_*`, or seeing
0020 say "Pattern" while everything else says "Look", will ask why. This is the answer: the first names were
abstract, the user's word is **Look**, and the rename was free because the schema had not yet shipped.
