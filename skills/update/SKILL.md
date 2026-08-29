---
name: update
description: "Re-syncs everything PILOT-owned that lives in a project's own git tree — docs/pilot-process.md, the PILOT:INTRO blocks in CLAUDE.md/README.md, the status-cascade GitHub Actions workflow, and the GitHub labels — from this plugin's current version, and propagates any skill/agent renames logged since the project's last sync. Overwrites, with no merge: any local edits inside a PILOT-owned file/block are lost, so it shows a diff and asks for confirmation before overwriting each one. Does not touch skills or agent personas — those are distributed by the plugin itself and sync automatically through Claude Code's own plugin update mechanism. Use after updating the pilot plugin, to pick up process-doc, intro-text, rename, or label changes in the project."
disable-model-invocation: true
---

# PILOT maintenance — `update`

Not one of the five PILOT phases, and not `init-archi`/`init`'s one-time setup — this is
the ongoing maintenance command, safe to run repeatedly.

## What this does and does not touch

- **Skills and agent personas** (`skills/*`, `agents/pilot-*.md`) are provided by the
  `pilot` plugin itself. When the plugin is updated (via Claude Code's own plugin update
  flow), these sync automatically — this command does not need to, and does not, touch
  them directly. It does, however, help a project catch up with *renames* of them — see
  step 5 below — since a rename changes references scattered across the project's own
  docs, which the plugin update flow has no way to reach.
- **`docs/pilot-process.md`** and **`.github/workflows/pilot-status-on-merge.yml`** in
  the project are verbatim copies of this plugin's own
  `${CLAUDE_PLUGIN_ROOT}/assets/docs/pilot-process.md` and
  `${CLAUDE_PLUGIN_ROOT}/assets/github/workflows/pilot-status-on-merge.yml`, made by
  `/pilot:init`. This command re-copies both, **overwriting the project's copies with no
  merge**. If someone hand-edited either file, those edits are lost. This is by design —
  both files are PILOT-owned, not project-owned — but it's a real risk of losing
  someone's work, so never skip the confirmation step below.
- **The `<!-- PILOT:INTRO:START -->`/`END` blocks** in the project's `CLAUDE.md` and
  `README.md` are the same kind of PILOT-owned content, just embedded inside otherwise
  project-owned files rather than being whole files of their own — see step 3.
- **GitHub labels** are re-applied idempotently (create-or-update, never delete) — safe
  to always re-run.

## Steps

1. **Check preconditions.** Read `.pilot/state.json`. If missing or `pilotInitialized`
   is not `true`, stop and tell the human to run `/pilot:init` first.

2. **Diff the two PILOT-owned files.** Compare the project's `docs/pilot-process.md` and
   `.github/workflows/pilot-status-on-merge.yml` against this plugin's
   `${CLAUDE_PLUGIN_ROOT}/assets/docs/pilot-process.md` and
   `${CLAUDE_PLUGIN_ROOT}/assets/github/workflows/pilot-status-on-merge.yml`
   respectively. For each one that differs, show the human a summary of the diff and ask
   for explicit confirmation before overwriting — call out plainly that any local edits
   on their side of the diff will be lost once they confirm. A file identical to the
   plugin's copy needs no confirmation. On confirmation, copy the plugin's version over
   the project's; on decline, leave it untouched and say so — a decline on one file must
   never block overwriting the other, or block steps 3-5.

3. **Diff the PILOT:INTRO blocks.** For each of `CLAUDE.md` and `README.md` at the
   project root:
   - If the file has no `<!-- PILOT:INTRO:START -->` marker, it predates this
     convention (or was hand-authored before the project adopted the `pilot` plugin).
     Don't guess where to insert one — report that this file has no managed intro block
     and skip it, unless the human explicitly asks you to locate the equivalent PILOT
     paragraph/section by hand and wrap it in markers now (a one-time fixup, not
     something to do silently).
   - If it has the markers, compare the content between them against
     `${CLAUDE_PLUGIN_ROOT}/assets/templates/pilot-intro-claude.md.tmpl` (for
     `CLAUDE.md`) or `pilot-intro-readme.md.tmpl` (for `README.md`). If it differs, show
     the diff and ask for confirmation before replacing the block's contents — same
     no-merge, no-silent-overwrite treatment as step 2. Never touch anything outside the
     markers.

4. **Re-provision GitHub labels.** Resolve the repo (`gh repo view --json
   nameWithOwner --jq .nameWithOwner`) and run
   `${CLAUDE_PLUGIN_ROOT}/scripts/setup-github-labels.sh <owner>/<repo>`.

5. **Propagate skill/agent renames.** Read the plugin's current version from
   `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`'s `version` field, and the
   project's `lastSyncedPluginVersion` from `.pilot/state.json`. Read
   `${CLAUDE_PLUGIN_ROOT}/assets/renames.json` and select every entry whose `since` is
   newer than `lastSyncedPluginVersion` (skip this step entirely if there are none, or if
   `lastSyncedPluginVersion` is missing — report that a version couldn't be determined
   and move on rather than guessing which renames apply).
   For each selected rename:
   - `to` is a new name (a skill/agent was renamed): search the project (at minimum
     `CLAUDE.md`, `README.md`, `docs/pilot-process.md` won't need it since step 2 already
     replaced it wholesale, but do check other project docs and any `.claude/`-local
     files) for `/pilot:<from>` and bare `` `<from>` `` mentions, and propose replacing
     them with `/pilot:<to>` / `` `<to>` ``. Show what would change per file and ask for
     confirmation before editing — this is prose in files the project otherwise owns, not
     a PILOT-owned block, so be conservative: skip a match that reads ambiguous (e.g. the
     word appears as part of a longer identifier, or the surrounding sentence doesn't
     actually mean the command/agent) rather than guessing.
   - `to` is `null` (the skill/agent was removed, no direct replacement): search the same
     way for `/pilot:<from>` mentions and flag each one to the human with the rename
     entry's `note` — don't auto-edit, since there's no mechanical replacement, only
     rewording, and that needs a human's judgment about what the surrounding sentence
     should say instead.
   Report every rename applied, skipped, or merely flagged.

6. **Update the state marker.** Set `lastProcessDocSyncAt`/`lastLabelsSyncAt` (only for
   what actually changed in steps 2 and 4), `lastIntroSyncAt` (if step 3 changed
   anything), and `lastSyncedPluginVersion` to the plugin's current version (from step 5)
   in `.pilot/state.json`.

7. **Report.** Summarize what changed across steps 2-5 (each file/block overwritten or
   left as-is and why, labels created/updated, renames applied/skipped/flagged), and
   remind the human that skills/agents themselves track the plugin version independently.
