# Leary D:\Tools triage (decision 8 — triage, not mirror)

Inventory taken 2026-08-18 (Session R1). Dispositions are RECOMMENDATIONS —
Andy confirms before anything moves or is deleted.

| Dir | Size | Last touched | On watts? | Recommended disposition |
|---|---|---|---|---|
| `dev\fleet_skills` | 56.9 MB | 2026-07-06 | ✅ cloned 2026-08-18 | KEEP as clone. Git is the mirror; watts is primary. |
| `mocap_runner` | 534.4 MB | **2026-08-16** | ✅ diverged copy | ⚠️ **Active divergence — highest risk.** Recently touched on BOTH machines. Needs a diff + git-ification with one canonical head before wave-2 migration. Do NOT hand-merge; diff first. |
| `fleet_helpers` | ~0 MB | 2026-06-23 | ✅ copy exists | Diff vs watts, git-ify, one head. Now also hosts `leary_harvest_push.ps1` (created R1). |
| `promise_ayon` | 20.1 MB | 2026-07-16 | ❌ (watts has `ayon_deploy`) | Move to `D:\Projects\Promise_RnD` orbit or merge into ayon_deploy's repo. It's project material, not a fleet tool. |
| `bin` | 75.3 MB | 2026-06-15 | ❌ | Inventory contents; likely leary-local utilities — keep local, document in leary's own CLAUDE.md. |
| `src` | 0.3 MB | 2026-06-24 | ❌ | Inspect; probably experiments → archive or fold into a repo. |
| `butterfly_diagrams` | 0.3 MB | 2026-07-16 | ❌ | Move to `D:\Projects\Butterfly` (its project home) on watts. |
| `.agents`, `.claude` | ~0.2 MB | 2026-07/08 | n/a | Leary-local session config — leave. |

## Related cleanups spotted during R1

- **`C:\Users\ajorl\fleet_skills` on watts** — stale third clone (same HEAD, no
  divergent commits, only untracked `.claude/`/`.agents/`). Delete after
  salvaging any wanted session config from those untracked dirs. KG already
  retired its location fact.
- **`D:\Tools\CLAUDE.md` (watts+leary)** — fleet-wide content now lives in
  `~/.claude/CLAUDE.md` on both machines (deployed R1). The Tools copy should
  shrink to Tools-local content — BUT its header says it's "synced" between
  machines by an unidentified mechanism. Identify that sync before editing, or
  edits may be clobbered/propagated unexpectedly.
- **Watts palace harvest is a one-shot** — `~/fleet_mine/watts/harvest` on
  mckenna has no recurring feeder (no push script exists on watts). Leary now
  pushes nightly (3:00 AM task → 3:30 AM mine); watts deserves the same
  `leary_harvest_push.ps1` pattern adapted, or the palace permanently lags
  watts reality.
