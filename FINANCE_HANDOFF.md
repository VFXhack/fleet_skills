# Finance handoff pointer (2026-09-07)

The household finance automation (`family_cfo`) does **not** live in this repo. This file exists because
fleet_skills is public and every fleet box already has a clone, so it is the reliable doorway.

- Code + full handoff: private repo `VFXhack/philosopher-fleet-tools`, branch `feat/family-cfo`,
  `apps/family_cfo/HANDOFF.md` (start there; it covers getting the branch onto leary/watts, the
  start-here steps, the MemPalace check, and the decisions queue).
- Plan, goals, daily log (Notion): https://app.notion.com/p/3d498bb138fa810d9b38d4a43e1cff55
- Runtime: Hermes cron on ramdass. Secrets: `~/.family_cfo/config.toml` per host. Nothing here touches
  the pipeline spine.

Kickoff for a CLI session on leary or watts:

```
Fetch feat/family-cfo of VFXhack/philosopher-fleet-tools (via GitHub if leary has creds, else via watts →
mckenna mirror), read apps/family_cfo/HANDOFF.md, and start at "Single next action".
```
