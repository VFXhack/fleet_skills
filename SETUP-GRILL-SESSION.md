# SETUP — get the grill session running

Four steps. Do them in order. ~20–30 min total before you're grilling.

---

## 1. Install the grill skill

The skill comes from Matt Pocock's skills repo. **`/grill-with-docs`** is the one you
want (it reads + updates `CONTEXT.md` and ADRs — perfect since this is now a codebase).
`/grill-me` is the no-codebase version.

```bash
# clone Matt's skills repo somewhere outside this project
git clone https://github.com/mattpocock/skills.git ~/src/mattpocock-skills
```

Then install per that repo's README. It's distributed as Claude Code commands/skills, so
it's one of these (the README will say which — follow it):

- **Agent Skill:** copy the `grill-with-docs` folder into `~/.claude/skills/`
  (personal, all projects) or `./.claude/skills/` (just this repo).
- **Slash command:** copy `grill-with-docs.md` into `~/.claude/commands/`
  (personal) or `./.claude/commands/` (this repo).

Verify: open Claude Code and type `/` — you should see `grill-with-docs` in the list.

> If unsure, install at the **personal** level (`~/.claude/...`) so it's available everywhere.

---

## 2. Create + push the GitHub repo

This scaffold currently lives in your `AO_Productivity` folder. Move or copy the
`fleet-skills` folder to your **workstation dev directory** first — the box you run
Claude Code on. **Not Mckenna** (that's infra: DBs + Flamenco, not your dev checkout).

```bash
cd ~/dev/fleet-skills        # wherever you put it
git init
git add .
git commit -m "Seed: CONTEXT, create-project + depth-pass skills, ADR 0001"

# with the GitHub CLI (easiest):
gh repo create fleet-skills --private --source=. --remote=origin --push
```

Manual fallback (no `gh`): create an empty `fleet-skills` repo on github.com, then:

```bash
git remote add origin git@github.com:<you>/fleet-skills.git
git branch -M main
git push -u origin main
```

GitHub is now **canonical**; this local clone is your working copy.

---

## 3. Where to start the Claude Code session

Start it at the **root of your local `fleet-skills` clone**:

```bash
cd ~/dev/fleet-skills
claude
```

Why here: `grill-with-docs` looks for `CONTEXT.md` in the working directory, and this repo
*is* the bounded context. If you want the agent to cross-reference existing pipeline code
during the grill, mention those paths in chat (or start where they're reachable) — but the
language work belongs here.

---

## 4. Kick off the grill

Open `GRILL_KICKOFF_PROMPT.md`, copy the prompt block, paste it into the session. The agent
will read `HANDOFF.md` + `CONTEXT.md` + the ADR, then start grilling you through the open
questions and update the docs as you go.

---

### After the session
Commit what the agent changed:

```bash
git add CONTEXT.md adr/
git commit -m "Session 1: sharpen UL + ADRs"
git push
```

That's Session 1 (calendar block: Fri Jun 26, 1:00 PM) done.
