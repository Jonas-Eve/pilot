---
name: init
description: "One-time bootstrap for a new project adopting PILOT: asks for the project name and a short functional vision, generates the project's own CLAUDE.md, README.md, and PROJECT-FUNCTIONAL-SCOPE.md from templates, copies in the canonical docs/pilot-process.md, and provisions the GitHub labels the state machine depends on. Refuses to run twice — if the project is already initialized, it stops with an explicit message instead of touching anything. Use when a human wants to start using PILOT in a project that hasn't run it before. Not for describing the monorepo's apps/technologies — that's /pilot:init-archi, and it requires this to have run first."
argument-hint: "[project name] [functional vision]"
disable-model-invocation: true
---

# PILOT bootstrap — `init`

This is not one of the five PILOT phases — it's the one-time setup that makes the rest
of the plugin usable in a project. Read `${CLAUDE_PLUGIN_ROOT}/assets/docs/pilot-process.md`
if you haven't already; it's what gets copied into the project by this skill.

## State marker

This skill's idempotency is tracked in `.pilot/state.json` at the project root:

```json
{
  "pilotInitialized": true,
  "pilotInitializedAt": "<ISO8601>",
  "projectName": "<name>",
  "archInitialized": false,
  "archInitializedAt": null,
  "lastProcessDocSyncAt": "<ISO8601>",
  "lastLabelsSyncAt": "<ISO8601>",
  "lastIntroSyncAt": "<ISO8601>",
  "lastSyncedPluginVersion": "<semver, from the plugin's own plugin.json at the time of this sync>"
}
```

`lastSyncedPluginVersion` is what `/pilot:update` compares against the plugin's current
version to decide which entries in `assets/renames.json` are new since the last sync —
see `skills/update/SKILL.md`.

## Steps

1. **Check for a prior run.** Read `.pilot/state.json`. If it exists and
   `pilotInitialized` is `true`, **stop here** and report, verbatim in substance:
   > PILOT is already initialized for this project ("<projectName>", on
   > <pilotInitializedAt>). Nothing to do — `init` only runs once. To pick up
   > PILOT's own file updates, use `/pilot:update`. To change the functional vision,
   > edit `PROJECT-FUNCTIONAL-SCOPE.md` directly.
   Do not write, overwrite, or re-run anything else in that case.

2. **Gather inputs.** Take the project name and functional vision from the arguments if
   given; otherwise ask the human for both. The functional vision should be a short
   paragraph (2-5 sentences) — enough to seed `PROJECT-FUNCTIONAL-SCOPE.md`'s "Vision"
   section and the one-line summary at the top of `CLAUDE.md`/`README.md`, not a full
   spec (the human fills in "In scope"/"Out of scope" in `PROJECT-FUNCTIONAL-SCOPE.md`
   themselves, later, as the product takes shape).

3. **Check for pre-existing root docs.** If `CLAUDE.md`, `README.md`, or
   `PROJECT-FUNCTIONAL-SCOPE.md` already exist at the project root (a project retrofitting
   PILOT onto existing work, as opposed to a brand-new empty repo), do **not** silently
   overwrite them. Show the human a diff/summary of what the generated version would
   contain and ask whether to overwrite, or skip that specific file and let them merge
   the PILOT-relevant sections in by hand. Never guess silently either way.

4. **Render templates.** For each of
   `${CLAUDE_PLUGIN_ROOT}/assets/templates/CLAUDE.md.tmpl`,
   `${CLAUDE_PLUGIN_ROOT}/assets/templates/README.md.tmpl`, and
   `${CLAUDE_PLUGIN_ROOT}/assets/templates/PROJECT-FUNCTIONAL-SCOPE.md.tmpl`, substitute
   `{{PROJECT_NAME}}` and `{{FUNCTIONAL_VISION}}` with the gathered values, and
   `{{PILOT_INTRO_CLAUDE}}` / `{{PILOT_INTRO_README}}` with the verbatim contents of
   `${CLAUDE_PLUGIN_ROOT}/assets/templates/pilot-intro-claude.md.tmpl` /
   `pilot-intro-readme.md.tmpl` respectively (inside their `<!-- PILOT:INTRO:START -->`/
   `END` markers — keep those markers in the output, they're what `/pilot:update` looks
   for later). Write the result to the project root (`CLAUDE.md`, `README.md`,
   `PROJECT-FUNCTIONAL-SCOPE.md`), respecting step 3's per-file decision. The
   `<!-- PILOT:ARCHITECTURE:START -->` and `<!-- PILOT:COMMANDS:START -->` marker blocks
   in `CLAUDE.md`/`README.md` are left as their template placeholder text —
   `/pilot:init-archi` fills those in later.

5. **Copy the process doc.** Copy
   `${CLAUDE_PLUGIN_ROOT}/assets/docs/pilot-process.md` to `docs/pilot-process.md` at the
   project root, creating `docs/` if needed. This file is PILOT-owned from here on —
   never hand-edit it in the project; `/pilot:update` overwrites it from the plugin.

5a. **Copy the status-cascade workflow.** Copy
   `${CLAUDE_PLUGIN_ROOT}/assets/github/workflows/pilot-status-on-merge.yml` to
   `.github/workflows/pilot-status-on-merge.yml` at the project root, creating
   `.github/workflows/` if needed. `docs/pilot-process.md` §6 depends on this workflow
   existing — without it, merged PRs and closed issues never cascade to `status:done`.
   It's PILOT-owned like the process doc: never hand-edit it; `/pilot:update` overwrites
   it from the plugin. If a workflow file of that name already exists and differs, treat
   it like step 3 — show the human what would change and ask before overwriting.

6. **Provision GitHub labels.** Determine the target repo (`gh repo view --json
   nameWithOwner --jq .nameWithOwner`) and run
   `${CLAUDE_PLUGIN_ROOT}/scripts/setup-github-labels.sh <owner>/<repo>`. If `gh` isn't
   authenticated or the repo can't be resolved, tell the human and give them the exact
   command to run themselves later — don't block the rest of this skill on it.

7. **Write the state marker.** Read the plugin's own version from
   `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`'s `version` field. Create
   `.pilot/state.json` per the schema above, with `pilotInitialized: true`, the current
   timestamp, the project name, `lastSyncedPluginVersion` set to that version,
   `lastIntroSyncAt` set to now, and `lastProcessDocSyncAt`/`lastLabelsSyncAt` set to now
   (or left null if step 6 was skipped).

8. **Report.** Summarize what was created/updated/skipped, and suggest running
   `/pilot:init-archi` next to describe the monorepo's apps and generate their scaffolds.
