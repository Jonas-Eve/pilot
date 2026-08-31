---
name: pilot-update
description: "Re-syncs everything PILOT-owned in a project from a fresh clone of github.com/Jonas-Eve/pilot — every skill under .claude/skills/ and agent under .claude/agents/, docs/pilot-process.md and its human-facing companion docs/pilot-process-visual.md, the status-cascade GitHub Actions workflow, the PILOT:INTRO/PILOT:MAINTENANCE marked blocks in CLAUDE.md/README.md, and the GitHub labels. Overwrites, with no merge: any local edits to a PILOT-owned file are lost, so it diffs and confirms before overwriting each one, and flags any locally-copied skill/agent no longer existing upstream (renamed or removed) for removal. Use periodically, or whenever you suspect PILOT's own skills/docs/labels have changed upstream, to pick up those changes in the project."
disable-model-invocation: true
---

# PILOT maintenance — `pilot-update`

Not one of the six PILOT phases, and not `pilot-init`/`pilot-init-archi`'s one-time setup —
this is the ongoing maintenance command, safe to run repeatedly.

## Get a fresh copy of the source repo

Same as `pilot-init`: clone (or re-clone) `https://github.com/Jonas-Eve/pilot` into a
scratch directory — call it `$PILOT_SRC` — and use that one clone for every step. Always
re-clone fresh (or `git pull` an existing scratch clone) rather than reuse a stale one
from a previous run — the whole point is picking up upstream changes.

## What this does and does not touch

- **Every skill under `.claude/skills/`** whose directory name matches one that exists
  under `$PILOT_SRC/.claude/skills/` (i.e. every PILOT skill: `pilot-story`, `pilot-scope`,
  `pilot-spec`, `pilot-dev`, `pilot-review`, `pilot-qa`, `pilot-init`, `pilot-init-archi`,
  `pilot-update`) — and every agent under `.claude/agents/` matching
  `$PILOT_SRC/.claude/agents/pilot-*.md` — are PILOT-owned. This command re-copies all of them
  verbatim from `$PILOT_SRC`, **overwriting with no merge**. If a project-local skill or
  agent directory doesn't match anything under `$PILOT_SRC` (the project's own, unrelated
  skill), leave it alone — touch only what's actually PILOT's.
- **`docs/pilot-process.md`**, **`docs/pilot-process-visual.md`** (a purely human-facing
  companion — no skill or agent reads it), and **`.github/workflows/pilot-status-on-merge.yml`**
  are the same kind of PILOT-owned file, made by `pilot-init` from `$PILOT_SRC`.
- **The `<!-- PILOT:INTRO:START -->`/`END` and `<!-- PILOT:MAINTENANCE:START -->`/`END`
  blocks** in the project's `CLAUDE.md` and `README.md` are PILOT-owned content embedded
  inside otherwise project-owned files —
  see step 4.
- **GitHub labels** are re-applied idempotently (create-or-update, never delete) — safe
  to always re-run.
- **`.github/pull_request_template.md`** is explicitly **not** PILOT-owned, even though
  `pilot-init` copies it in from `$PILOT_SRC/assets/github/pull_request_template.md`. It's
  a one-time scaffold, not a synced asset: this command never diffs, touches, or reports
  on it, so the project is free to customize it however it likes.
- Anything hand-edited inside a PILOT-owned file/block is lost on overwrite — that's why
  every step below diffs and confirms first, never overwrites silently.

## Steps

1. **Check preconditions.** Read `.pilot/state.json`. If missing or `pilotInitialized`
   is not `true`, stop and tell the human to run `/pilot-init` first.

2. **Diff and sync skills/agents.** For each directory under `$PILOT_SRC/.claude/skills/` and
   each file under `$PILOT_SRC/.claude/agents/`:
   - If the project has no matching `.claude/skills/<name>/` or `.claude/agents/<name>`,
     it's new upstream — copy it in and mention it in the final report as newly added.
   - If the project has a matching one and its content differs, show a diff and ask for
     confirmation before overwriting (same no-merge treatment as any other PILOT-owned
     file). Identical content needs no confirmation.
   Then check the reverse direction: for each `.claude/skills/pilot-*` or `.claude/skills/pilot-init-archi`
   and `.claude/agents/pilot-*.md` the project has, if nothing matching exists under
   `$PILOT_SRC` any more (renamed or removed upstream), flag it to the human as orphaned
   and ask before deleting — don't delete silently, and don't guess at a replacement name;
   if the human knows what it was renamed to, let them say so.

3. **Diff the PILOT-owned root files.** Compare the project's `docs/pilot-process.md`,
   `docs/pilot-process-visual.md`, and `.github/workflows/pilot-status-on-merge.yml`
   against `$PILOT_SRC`'s copies. For each one that differs, show a diff and ask for
   confirmation before overwriting. A file identical to `$PILOT_SRC`'s needs no
   confirmation. On confirmation, copy `$PILOT_SRC`'s version over the project's; on
   decline, leave it untouched and say so — a decline on one file must never block
   overwriting another, or block steps 2, 4, or 5.

4. **Diff the marked blocks.** For each `(file, marker, canonical snippet)` triple —
   `(CLAUDE.md, PILOT:INTRO, pilot-intro-claude.md.tmpl)`,
   `(README.md, PILOT:INTRO, pilot-intro-readme.md.tmpl)`,
   `(CLAUDE.md, PILOT:MAINTENANCE, pilot-maintenance-claude.md.tmpl)`:
   - If the file has no `<!-- PILOT:<marker>:START -->` marker, it predates this
     convention (or was hand-authored before the project adopted PILOT). Don't guess
     where to insert one — report that this file has no managed block of that kind and
     skip it, unless the human explicitly asks you to locate the equivalent PILOT
     paragraph/section by hand and wrap it in markers now (a one-time fixup, not
     something to do silently).
   - If it has the markers, compare the content between them against
     `$PILOT_SRC/assets/templates/<canonical snippet>`. If it differs, show the diff and
     ask for confirmation before replacing the block's contents — same treatment as step
     3. Never touch anything outside the markers.
   These blocks aren't limited to the three above — if this repo's own templates gain
   another `PILOT:<name>:START`/`END` marker later, treat it the same way.

5. **Re-provision GitHub labels.** Resolve the repo (`gh repo view --json
   nameWithOwner --jq .nameWithOwner`) and run
   `$PILOT_SRC/scripts/setup-github-labels.sh <owner>/<repo>`.

6. **Update the state marker.** Set `lastSkillsSyncAt` (if step 2 changed anything),
   `lastProcessDocSyncAt` (if step 3 changed any of its three files),
   `lastIntroSyncAt` (if step 4 changed anything), and `lastLabelsSyncAt` (step 5) in
   `.pilot/state.json` to now.

7. **Report.** Summarize what changed across steps 2-5: skills/agents added, updated,
   flagged as orphaned (and whether removed), each root file overwritten or left as-is
   and why, intro blocks resynced or skipped, labels created/updated.
