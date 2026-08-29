---
name: update
description: "Re-syncs the PILOT files that get copied into a project's own git tree — docs/pilot-process.md and the GitHub labels — from this plugin's current version. Overwrites, with no merge: any local edits to docs/pilot-process.md are lost, so it shows a diff and asks for confirmation before overwriting. Does not touch skills or agent personas — those are distributed by the plugin itself and sync automatically through Claude Code's own plugin update mechanism. Use after updating the pilot plugin, to pick up process-doc or label changes in the project."
disable-model-invocation: true
---

# PILOT maintenance — `update`

Not one of the five PILOT phases, and not `init-archi`/`init`'s one-time setup —
this is the ongoing maintenance command, safe to run repeatedly.

## What this does and does not touch

- **Skills and agent personas** (`skills/pilot*`, `agents/pilot-*.md`) are provided by
  the `pilot` plugin itself. When the plugin is updated (via Claude Code's own plugin
  update flow), these sync automatically — this command does not need to, and does not,
  touch them.
- **`docs/pilot-process.md`** and **`.github/workflows/pilot-status-on-merge.yml`** in
  the project are verbatim copies of this plugin's own
  `${CLAUDE_PLUGIN_ROOT}/assets/docs/pilot-process.md` and
  `${CLAUDE_PLUGIN_ROOT}/assets/github/workflows/pilot-status-on-merge.yml`, made by
  `/pilot:init`. This command re-copies both, **overwriting the project's copies with no
  merge**. If someone hand-edited either file, those edits are lost. This is by design —
  both files are PILOT-owned, not project-owned — but it's a real risk of losing
  someone's work, so never skip the confirmation step below.
- **GitHub labels** are re-applied idempotently (create-or-update, never delete) — safe
  to always re-run.

## Steps

1. **Check preconditions.** Read `.pilot/state.json`. If missing or `pilotInitialized`
   is not `true`, stop and tell the human to run `/pilot:init` first.

2. **Diff both PILOT-owned files.** Compare the project's `docs/pilot-process.md` and
   `.github/workflows/pilot-status-on-merge.yml` against this plugin's
   `${CLAUDE_PLUGIN_ROOT}/assets/docs/pilot-process.md` and
   `${CLAUDE_PLUGIN_ROOT}/assets/github/workflows/pilot-status-on-merge.yml`
   respectively. For each one that differs, show the human a summary of the diff and ask
   for explicit confirmation before overwriting — call out plainly that any local edits
   on their side of the diff will be lost once they confirm. A file identical to the
   plugin's copy needs no confirmation.

3. **Overwrite on confirmation.** For each file confirmed, copy the plugin's version
   over the project's. For any file the human declines, leave it untouched and say so —
   don't silently proceed, and don't let a decline on one file block overwriting the
   other.

4. **Re-provision GitHub labels.** Resolve the repo (`gh repo view --json
   nameWithOwner --jq .nameWithOwner`) and run
   `${CLAUDE_PLUGIN_ROOT}/scripts/setup-github-labels.sh <owner>/<repo>`.

5. **Update the state marker.** Set `lastProcessDocSyncAt` (only if step 3 actually
   overwrote) and `lastLabelsSyncAt` in `.pilot/state.json` to now.

6. **Report.** Say what changed (each of the two files overwritten or left as-is and
   why, labels created/updated) and remind the human that skills/agents track the plugin
   version independently.
