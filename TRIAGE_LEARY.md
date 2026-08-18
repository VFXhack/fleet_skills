# Leary D:\Tools triage — EXECUTED 2026-08-18 (Session R1)

Inventory taken and dispositions executed 2026-08-18 with Andy's go-ahead.
One major correction vs. the original sheet: **mocap_runner was never diverged.**

| Dir | Size | Status | What was done |
|---|---|---|---|
| `dev\fleet_skills` | 57 MB | ✅ done | Clone; pulled to R1 head. Watts is primary (`D:\Tools\dev\fleet_skills`). |
| `mocap_runner` | 534 MB | ✅ done — **sheet was wrong** | BOTH machines were already clones of `VFXhack/mocap_runner`, in sync at `f7deb7c`. The "divergence" was CRLF checkout normalization (69 files, zero real diffs after normalizing — verified by normalized md5) + ~500 MB of gitignored QC render PNGs (`qc_batch/`, leary-local data). Committed watts' untracked `BERNINI_GUIDE.md` + `.gitattributes` (`* text=auto`), pushed `580ce59`, pulled on leary. |
| `fleet_helpers` | tiny | ✅ done | Was NOT a repo on either side; file sets were disjoint (watts: cutter app + watts scripts; leary: leary/sshd scripts + new `leary_harvest_push.ps1`). Union-merged → new private repo **`VFXhack/fleet_helpers`** (`79f0d75`), both machines now clones. Harvest-push scheduled task path verified intact. |
| `promise_ayon` | 20.1 MB | ✅ done | Copied to `watts:D:\Projects\Promise_RnD\promise_ayon` (640 files / 21,105,141 bytes, byte-verified). Leary original renamed `promise_ayon._migrated_2026-08-18` — delete whenever. |
| `butterfly_diagrams` | 0.3 MB | ✅ done | Copied to `watts:D:\Projects\Butterfly\butterfly_diagrams` (4 files, byte-verified). Leary original renamed `._migrated_2026-08-18`. |
| `bin` | 75 MB | ✅ keep local | It's `rclone.exe` + mount log. Leary-local utility, nothing to sync. |
| `src` | 0.3 MB | ✅ keep local | Reference checkout of `mattpocock-skills` (the grill-with-docs upstream). Third-party, stays local. |
| `.agents`, `.claude` | ~0.2 MB | ✅ leave | Leary-local session config. |

## Related cleanups — status

- **`C:\Users\ajorl\fleet_skills`** — ✅ DELETED. Untracked `.claude/`, `.agents/`,
  `skills-lock.json` archived first (66 files →
  `D:\Tools\_archive\fleet_skills_userprofile_clone_2026-08-18\`). KG fact
  already retired.
- **`D:\Tools\CLAUDE.md` trim** — ⏳ still open. Fleet content now lives in
  `~/.claude/CLAUDE.md` on both machines; identify the Tools-file sync
  mechanism before shrinking it.
- **Watts palace harvest** — ⏳ still one-shot. Leary pushes nightly
  (`fleet_harvest_push` 3:00 AM); watts needs the same pattern or the palace
  permanently lags watts.
- **`comfy_runner` is not a git repo** — 📌 new find. It's a wave-1-adjacent
  tool (the LTX submitter) with no version control; git-ify before its lane
  migrates.
