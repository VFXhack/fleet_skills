# ADR Reality Audit — Session R1 (2026-08-18)

**Method:** every ADR (0001–0024) judged against six weeks of production that happened
outside this system (2026-07-06 → 2026-08-18): shotgate (now the fleet review server),
comfy_runner, the zombo v002 lanes (M8 latent multi-stage, flux2 polish, LTX union
control, depthwire control passes, bernini, magnific, the nobg-singletons stills v2
pipeline), and the 3z_ltx_union_roll2_bw provenance forensics (2026-08-18). Governing
decisions: `RECONCILIATION_BRIEF.md`.

**Verdict key:** HOLDS · AMEND · BROKEN-BY-REALITY · SUPERSEDED-BY-SHOTGATE · UNTESTED

## Summary

| ADR | Title | Verdict |
|---|---|---|
| 0001 | Skills vs Spells, Spellbook | HOLDS (unexecuted — Spellbook folder never created) |
| 0002 | Project store on Huxley | BROKEN-BY-REALITY → grill |
| 0003 | Canonical project structure | AMEND (canon for new jobs; production never migrated) |
| 0004 | Reconciliation with prior UL | HOLDS (historical record) |
| 0005 | Artifact/versioning/provenance | HOLDS — strongly validated by the 3Z forensics |
| 0006 | Thin Manifest | HOLDS (round-trip proven Session 9) |
| 0007 | Recipe hybrid (Run + frozen submission) | HOLDS — validated by the embedded-workflow save |
| 0008 | Provenance core: Postgres on Mckenna | HOLDS — CONFIRMED by reality; amend for coexistence (draft 0025) |
| 0009 | Spellbook in repo | HOLDS (unexecuted; six weeks of craft is the backlog) |
| 0010 | Conductor separate from Submitter | HOLDS (as amended by 0012) |
| 0011 | Physical schema | HOLDS; AYON mapping check before further migrations (draft 0027) |
| 0012 | Ringmaster over Roustabout | AMEND — review-surface duties move to shotgate (draft 0026) |
| 0013 | VersionRecorded after landing | HOLDS — rediscovered operationally as the batch-watcher rule |
| 0014 | run.type single dispatch key | HOLDS; wave-1 stress test (M8 / nobg-convert don't fit cleanly) |
| 0015 | Shot code JOB_EP_SEQ_SHOT | HOLDS as convention; ignored in practice → enforce via proving lane |
| 0016 | Per-run-type spec | HOLDS (expand proven; sweep grammar matches real sweeps) |
| 0017 | control-pass generalizes depth-pass | HOLDS — the depthwire chroma bug is this ADR's poster child |
| 0018 | Roustabout FLOWS | SUPERSEDED-BY-SHOTGATE (partially) — draft 0026 re-cuts it |
| 0019 | Events: NOTIFY + durable outbox | HOLDS — and it is the fix for shotgate's watcher failures |
| 0020 | Sequence Look / Hoist | UNTESTED — but zombo production followed its taxonomy by hand |
| 0021 | Look rename | HOLDS |
| 0022 | Hoist is publish-driven | HOLDS / UNTESTED live |
| 0023 | Override store | HOLDS / UNTESTED (7Z/9Z defect fixes are its use case) |
| 0024 | Submitter single responsibility | HOLDS — independently validated by comfy_runner |

---

## Per-ADR findings

### 0001 — Skills vs Spells · HOLDS (unexecuted)
The concept proved itself in a parallel guise: the watts Claude-skills ecosystem
(shotgate, kg-sync, grilling skills) grew exactly the way "Spell graduates into Skill"
predicts. But `spellbook/` was never created — six weeks of hardened craft accumulated
instead in `ENHANCE_PLAN.md`, `RECIPES_POM.md`, `BERNINI_GUIDE.md`, and per-project
CLAUDE.mds. **Action:** keep; wave-1 run-type codification (brief §5) IS the Spellbook
migration — those documents are the content.

### 0002 — Project store on Huxley · BROKEN-BY-REALITY
`create-project` proved the huxley store works (`\\huxley\io_common\projects\TEST\SANDBOX`,
Session 9). But all six weeks of real production ran from watts `D:\Projects\WBTV\AWA\…`
(and the leary mesh library), with huxley used as **compute** (ComfyUI :9110, diffusers)
whose outputs land in `io_common/output/` and get copied back to watts by hand. The "one
authoritative copy" never existed; meanwhile huxley's root disk is under pressure (238 GB
stray HF cache). **Action: GRILL** — recommit to the huxley store for the proving lane
(and actually move the zombo tree), or amend 0002 to "store on watts `D:\Projects`,
huxley = compute + scratch." Neither is free; the brief did not rule on this.

### 0003 — Canonical structure · AMEND
Confirmed canon Session 9 for new jobs; the reconciliation gap in HANDOFF (real projects
use `AI_Renders\<SHOT>\` etc.) got *worse*: zombo built a third shape
(`lora\zombo_v002\shot3z\{iso,m*_out,flux_polish,video}\`) — stage-named folders,
flat files, shotgate boards as the only structure. Note also `versions/{render,upscale,comp}`
may need a stage for the stills-v2 convert/matte steps. **Action:** keep as target;
the proving lane must run in a real ADR-0003 tree (grill question 2); add stage
vocabulary in wave 1 if needed.

### 0004 — Prior-UL reconciliation · HOLDS
Historical record; nothing in six weeks contradicts it.

### 0005 — Artifact model · HOLDS (strongly validated)
The 3Z forensics is this ADR's evidence file: `ms_k16_flux2_dn35.png` renamed to
`3z_hero_frm125.jpg` severed lineage exactly as "ephemeral address" predicts (recovered
only by pixel-match); shotgate keep/score verdicts are un-recorded Publishes; the LTX
render that survived audit did so only because ComfyUI embedded the workflow. Every
failure mode the ADR names occurred; every mechanism it prescribes would have prevented
one. AYON note: our **Publish ↔ AYON version** (AYON only versions published things),
our Version = pre-publish take — the mapping is natural (draft 0027). **Action:** keep.

### 0006 — Thin Manifest · HOLDS
`db_project_id` round-trip proven live (Session 9). Nothing contradicts.

### 0007 — Recipe hybrid · HOLDS (validated)
The frozen-submission concept saved this morning's audit: the mp4's embedded ComfyUI API
graph IS a frozen submission (resolved level), and `latent_ms.py`'s constants are the
authoring level. Where the pattern was absent (ffmpeg blends, rename, flux CLI args) the
audit hit dead ends. **Action:** keep; wave-1 sidecars = frozen submissions for
non-DB-routed steps until everything flows through submit.

### 0008 — Provenance core on Mckenna Postgres · HOLDS, CONFIRMED
Session 8 stood the DB up (PG 17, db `fleet`, migrations 0001–0003 prod;
`fleet_test` at 0005). Brief decision 10 independently re-derived this placement six
weeks later — convergent evidence, not conflict. What's new since: **mempalace's
pgvector store now runs on mckenna** (532k drawers) and Apricity reads mirrors of it;
mckenna is now state-critical with no backup story. Notion demotion is **unexecuted**:
comfy_runner still logs to Notion, the Video Generations log never migrated, and the
palace has emerged as a third memory surface. **Action:** amend via draft ADR 0025
(coexistence, boundary, backup); GRILL Notion's fate (question 3). Verify: prod
migrations 0004+0005 applied? same PG cluster as mempalace?

### 0009 — Spellbook in repo · HOLDS (unexecuted)
See 0001. The folder does not exist in the tree; the Notion migration never ran.
**Action:** create `spellbook/` in wave 1; first Spells = the stills-v2 chain steps,
the depthwire control blend (with the chroma fix), the flux2 polish recipe, the
magnific lanes.

### 0010 — Conductor separate · HOLDS
As amended by 0012. The reserved Hermes-on-Ramdass seat matches brief decision 12
exactly. **Action:** keep.

### 0011 — Physical schema · HOLDS
Migrations 0001–0005 exist and are proven vs `fleet_test`; expand/cast/hoist all write
against it. **Action:** keep; run the AYON mapping check (draft 0027) before authoring
further migrations; extend `versions.stage` only when the stills-v2 run-types demand it.

### 0012 — Ringmaster / Roustabout · AMEND
The two-floor concept holds (judgment vs deterministic). What changed: **shotgate**
now exists and owns exactly the human-facing half the Roustabout was scoped to produce
(contact sheets, notify, review). Production chose shotgate fleet-wide ("never write
bespoke review HTML/watchers"). **Action:** draft ADR 0026 re-cuts the seam — Roustabout
keeps ledger-side reactions (proxy, barrier, auto-publish, chains); shotgate owns
boards/watchers/verdicts as the review bounded context.

### 0013 — VersionRecorded after landing · HOLDS (rediscovered)
Production independently invented this rule as the **fleet batch-watcher rule** ("every
render batch gets a watcher at launch; no fire-and-forget") — the same insight: the
event that matters is *landing*, not dispatch. **Action:** keep; the events outbox
replaces filesystem watching as the landing signal (0026).

### 0014 — run.type dispatch enum · HOLDS (stress test in wave 1)
The week's real runs map well: s1001/s2025/s31337 = `seed-sweep`; flux dn 0.25–0.45
rungs and k8/12/16 splits = `xy-plot`/`prompt-variation`; depthwire = `control-pass`;
Topaz/Magnific = `upscale`. Two don't fit cleanly: **M8 latent multi-stage** (one gen
run with element sub-renders inside it) and the **nobg-convert** step (edit-model
conversion — neither refine-of-a-publish nor a sweep). Open-text column makes extension
cheap. **Action:** keep; wave-1 design question — new enum value(s) vs Spell-under-gen-type
(grill question 4).

### 0015 — Shot code JOB_EP_SEQ_SHOT · HOLDS as convention, ignored in practice
Zombo shots are `3Z/5Z/7Z/9Z` inside a lora directory; renders are `AWA_HORDE_7Z_v005…`.
No production artifact from six weeks carries a conformant code. **Action:** keep; the
proving lane assigns real codes at cast time — this is enforcement, not redesign.

### 0016 — Per-run-type spec · HOLDS
`expand` built and proven (Session 13); the sweep grammar (explicit values,
points-not-intervals) matches how `latent_ms_sweep.py` actually ran (8 masters from one
stage-1). Known gap already logged: spec not threaded through Hoist/Cast. **Action:** keep.

### 0017 — control-pass · HOLDS (poster child)
The depthwire driver is a `control-pass` with `spec.method` = the blend recipe — and the
six weeks provided the perfect cautionary tale: the recipe lived nowhere, the YUV
screen-blend chroma bug cost a full LTX roll (roll1 magenta), and the fix (blend control
passes in the gray plane, convert yuv420p LAST) exists only as prose in ENHANCE_PLAN.md.
Exactly what a versioned Spell prevents. **Action:** keep; write `spellbook/spells/`
entries for the depthwire family with the fix baked in (brief §5).

### 0018 — Roustabout FLOWS · SUPERSEDED-BY-SHOTGATE (partially)
Its per-run barrier ("N of N landed" → contact sheet + one notify) is *literally* what a
shotgate board + watcher does — and shotgate's production failure modes are precisely
what the outbox model fixes: watchers die silently on idle timeout (durable `events`
drain can't miss), and re-launched watchers mint duplicate boards
(`shotgate_board.video.json` beside `shotgate_board.zombo_3z_video.json` — board
identity should be the **run_id**, making board creation idempotent). Auto-publish
bounds and wired chains remain Roustabout territory (ledger-side, no UI). **Action:**
supersede via draft ADR 0026.

### 0019 — Events outbox · HOLDS
Built, proven end-to-end vs the live DB (Session 8). Becomes the transport that
replaces shotgate's filesystem polling. **Action:** keep; add shotgate as a consumer
(0026).

### 0020–0023 — Sequence Look / Hoist / Cast / Override · UNTESTED, shape-validated
Zombo unknowingly followed the model by hand: **3Z was the look-dev Shot** (the winning
stack developed there), `latent_ms_shot.py <shot>` was a manual **Hoist+Cast** (shared
recipe re-run per shot on 7Z/9Z), face tiles were **shared-content**, per-shot
elements/mattes were **per-shot**, and the 7Z/9Z defect repairs (headless fix, hair
drift) are textbook **Overrides**. The taxonomy predicted production behavior without
production knowing it existed. Hoist-anchors-on-a-Publish (0022) maps to "shotgate
keep/score-5 = the approval" — wiring verdicts to publishes (0026) makes it real.
**Action:** keep all four; the proving lane (5Z/7Z/9Z cast from the 3Z Look) is their
first real test. Known gaps stand: per-shot forward re-cast; spec threading.

### 0024 — Submitter single responsibility · HOLDS (independently validated)
comfy_runner converged on the same shapes from the practical side: API-format templates
+ per-workflow mappings (proto-Templates), sidecar JSON (proto-frozen-submission),
Notion logging (the demoted view). It bundles author+submit+log in one CLI — which is
exactly what ADR 0024 unbundles. And the run that **bypassed** it (3Z LTX, queued raw;
saved only by ComfyUI's embedded metadata) shows why submit must become the only door.
**Action:** keep; wave-1 integrates comfy_runner as the **ComfyUI Runner** (dispatch
backend) behind `submit`, its sidecar logic feeding `frozen_submission`.

---

## Contradictions the brief has NOT ruled on (grill questions for Andy)

1. **Project store location** (0002): recommit to the huxley canonical store (and move
   zombo into it) — or amend to watts `D:\Projects` as store, huxley as compute?
2. **Proving-lane home:** does the stills-v2 lane run inside a real ADR-0003 tree with
   real `JOB_EP_SEQ_SHOT` codes (a migration of the zombo shots), or bridge from the
   existing `zombo_v002` layout for phase 1?
3. **Notion's fate** (0008): comfy_runner still logs to Notion; the Video Generations
   log never migrated; MemPalace now exists as the narrative layer. Which surfaces
   survive: Postgres (records) + palace (prose) + Notion (client-facing view only)?
   Or is Notion fully retired?
4. **Run-type fit for the new recipes** (0014): M8 latent multi-stage and nobg-convert —
   new enum values, or Spells under an existing gen type? (Also: flux2 polish = `refine`
   or `upscale`?)
5. **Verdict/auto-publish authority** (0018/0026): do shotgate keep/winner verdicts
   become the ONLY human promote path (verdict → `promote()`)? Does control-pass
   auto-publish stay boardless?
6. **Ops verifications:** prod `fleet` at migration 0005? mempalace pgvector on the same
   PG 17 cluster as `fleet`? mckenna backup story (now a prerequisite, brief §10).

---

## Draft superseding / amending ADRs

### DRAFT ADR 0025 — The provenance core shares Mckenna's Postgres with MemPalace; backup becomes a prerequisite

**Status:** Proposed (R1)
**Amends:** ADR 0008 (placement confirmed, coexistence + ops added)

#### Context
ADR 0008 placed the provenance core on Mckenna Postgres; Session 8 stood it up (PG 17,
db `fleet`). Since then Mckenna also became home to the MemPalace fleet store (pgvector,
~532k drawers) and the Apricity dashboard. Two data systems with different jobs now share
one host — and the brief (decision 10) requires the boundary stated and the host backed up.

#### Decision
- The provenance core remains db **`fleet`** on Mckenna's PG 17 cluster, coexisting with
  MemPalace's database(s). One cluster, separate databases, separate roles.
- **Boundary:** Postgres `fleet` holds **records** (runs/versions/publishes/deliveries —
  structured, queryable, relational). MemPalace holds **narrative** (verdicts-as-prose,
  decisions, gotchas) fed by fleet_mine. Run records are never drawers; drawers are never
  provenance. A provenance report reads `fleet` and may *cite* palace drawers.
- Artifacts stay file-based (ADR 0002's store, wherever grill question 1 lands); the DB
  stores addresses, never pixels.
- **Prerequisite:** a real Mckenna backup story (nightly `pg_dump` of `fleet` + the
  palace DB to a second host at minimum) lands before the proving lane goes live.

#### Consequences
Mckenna is formally state-critical; its provisioning/backup is part of phase 1.
`fleet` migration state must be verified to 0005 before new writes.

### DRAFT ADR 0026 — Shotgate is the review bounded context; the Roustabout's human-facing duties move into it

**Status:** Proposed (R1)
**Amends:** ADR 0012, ADR 0018 · **Refines:** ADR 0019, 0022

#### Context
ADR 0018 gave the Roustabout contact-sheet assembly and notify duties. Since July,
**shotgate** (watts :8377, fleet-wide) became the production review surface — boards,
watchers, verdicts — and was promoted as THE review server. Running both means two
review surfaces and two event models. Shotgate's production failure modes (duplicate
boards per folder, watchers dying silently on idle timeout, server flake) are precisely
the problems ADR 0019's durable outbox was designed against.

#### Decision
- **Shotgate is the review bounded context** inside the system. It owns boards, contact
  sheets, watchers, human verdicts, and review notifications.
- **The Roustabout sheds its human-facing tier:** it keeps per-take ledger reactions
  (proxy/thumbnail, structured log), the per-run completion barrier, bounded
  auto-publish, and wired chains. On barrier completion it **notifies shotgate** to
  build/refresh the run's board instead of assembling a contact sheet itself.
- **Event-driven boards:** shotgate consumes `VersionRecorded` / `PublishRecorded` from
  the durable outbox (ADR 0019) instead of filesystem polling. A board's identity is the
  **run_id** — board creation is idempotent, killing the duplicate-board failure. The
  outbox's startup drain kills the silent-watcher-death failure (a down consumer misses
  nothing).
- **Verdicts flow back:** a shotgate keep/winner verdict on a Version calls the
  Submitter's `promote()` — the verdict IS the human Publish gate (and the Hoist anchor,
  ADR 0022). Verdicts are designed as publishable events (AYON publisher subscribes in
  phase 2 — brief decision 11).
- **Hardening scope (phase 1):** the duplicate-board fix, the event-consumer watcher
  replacement, and server stability (service-ification) are part of absorbing shotgate.

#### Consequences
One review surface, one event transport. Shotgate gains a DB consumer and a promote
call-path; the Roustabout shrinks (correct per ADR 0012's minimalism). Legacy
folder-watcher mode remains for non-spine renders until wave-2 migrations.

### DRAFT ADR 0027 — The provenance schema must map 1:1 onto AYON's entity model (design constraint, no AYON code)

**Status:** Proposed (R1)
**Refines:** ADR 0005, ADR 0011 · **Relates:** ADR 0008 (AYON rejected as the core — unchanged)

#### Context
ADR 0008 rightly rejected adopting AYON as the provenance core. But AYON is now real in
the business: a test server runs on huxley (:5000), GC_grayscale runs on the promise
server's AYON, and the accepted Promise pitch makes "Bid-to-AYON bootstrap" a committed
demo. Phase 2 will auto-publish shotgate keeps to AYON. If the schema drifts from AYON's
shape, that integration becomes a migration; if it maps, it's an exporter.

#### Decision
A standing **design constraint** on the provenance schema (checked at every migration):

| fleet_skills | AYON | Note |
|---|---|---|
| Project (`job_code`) | project | |
| Episode / Sequence / Shot (codes) | folder hierarchy | codes ↔ folder paths |
| Run + Version (`v###`) | workfile-side iterations | pre-publish; AYON never sees them |
| **Publish (`p###`)** | **product + version** | our gate = AYON's only unit; product name ≈ stage/Role |
| Delivery (client `v#`) | delivered/approved status on a version | |
| Version files (address, proxy) | representations | |
| frozen_submission / recipe | version attribs / metadata | travels as attribute payload |

- No AYON code in phase 1. The constraint is a review check: any schema change that has
  no AYON counterpart needs an explicit "phase-2 exporter handles it" note in its ADR.
- Shotgate verdicts (draft 0026) are the publish events an AYON publisher will subscribe to.

#### Consequences
Phase-2 AYON publisher is a mapping exercise, not a migration. The Promise demo
(bid → project bootstrap → publishes appearing in AYON) rides the same pipe as internal
provenance.
