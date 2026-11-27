---
name: pilot-update
description: "Re-syncs everything PILOT-owned in a project from a fresh clone of github.com/Jonas-Eve/pilot — skills, agents, .pilot/ scripts, formats.json, workflows and docs, the merge workflow, the PILOT:* marked blocks of CLAUDE.md/README.md, the GitHub labels, and the dashboard artifact when the project has one. Diffs and confirms before overwriting each file (no merge: local edits are lost), flags and removes what no longer exists upstream, and for a major release tells how to migrate existing tickets. Use periodically, or when PILOT may have changed upstream."
disable-model-invocation: true
---

# PILOT maintenance — `pilot-update`

The ongoing maintenance command, safe to run repeatedly.

## Source

Clone (or `git pull` a scratch clone of) `https://github.com/Jonas-Eve/pilot` fresh into a scratch
directory, `$PILOT_SRC`, and use it for every step. Never reuse a stale one.

## What is PILOT-owned

Copied verbatim by `pilot-init`, overwritten here with no merge:

| Project path | Source in `$PILOT_SRC` |
|---|---|
| `.claude/skills/<name>/`, `.claude/agents/pilot-*.md` | `.claude/skills/`, `.claude/agents/` |
| `.pilot/pilot.py`, `.pilot/pilot_checks.py` | `scripts/` |
| `.pilot/formats.json` | `assets/formats.json` |
| `.pilot/workflows/*.json` | `assets/workflows/` |
| `.pilot/pilot-*.md` | `assets/docs/pilot-*.md` |
| `.github/workflows/pilot-status-on-merge.yml` | `assets/github/workflows/` |
| `PILOT:*` blocks of `CLAUDE.md`/`README.md` | `assets/templates/pilot-<name>-{claude,readme}.md.tmpl` |
| the dashboard artifact | `assets/templates/pilot-dashboard.html.tmpl` |

Never touched: the project's own skills and agents (no match upstream), `wiki/`, `architecture/`,
`.github/pull_request_template.md`, anything outside the markers, `.pilot/state.json` beyond step 6.

## Steps

1. **Preconditions.** `.pilot/state.json` must exist with `pilotInitialized: true`, else point at `/pilot-init`.
   Note the current `pilotVersion` for the report.

2. **Sync files.** For every PILOT-owned path of the table (each glob is its own set, however many files exist):
   missing locally: copy it, report it as new (`chmod +x` the scripts); different: show the diff and ask before
   overwriting; identical: nothing. A decline never blocks another file or step.
   **Orphans:** any local `.claude/skills/pilot-*`, `.claude/agents/pilot-*.md`, `.pilot/workflows/*.json` or
   `.pilot/pilot-*.md` with nothing matching upstream is flagged and deleted only on confirmation, without guessing
   a replacement. `pilot.py doctor` lists the obsolete keys of `state.json`: remove them.

3. **Marked blocks.** For `(CLAUDE.md, INTRO)`, `(README.md, INTRO)`, `(CLAUDE.md, MAINTENANCE)`: no
   `<!-- PILOT:<name>:START -->` marker means the file predates the convention: report and skip (unless the
   human asks for a one-time fixup). With markers, diff the content between them against the template snippet and
   ask before replacing; never touch anything outside. `PILOT:ARCHITECTURE` and `PILOT:COMMANDS` may hold the
   project's own content: replace one only while it still holds the placeholder or an earlier copy of the pointer.
   Any other `PILOT:<name>` marker the templates gain is treated the same way.

4. **Labels.** `python3 .pilot/pilot.py labels sync` (create-or-update, never delete; stamps `lastLabelsSyncAt`).
   If `gh` is unavailable, give the human the command and go on.

5. **Modules and config.** `python3 .pilot/pilot.py module list`. A `state.json` with no `modules` predates them:
   in step 6 set `dashboard` on when it has a `dashboardUrl` (with `design` and `proto`), `wiki` off. Say which
   modules exist (`.pilot/pilot-process.md` §7) and that each is turned on by its own skill; enable nothing here,
   never change `wiki/` or `architecture/`. With `wiki` on and `wiki/` missing, `doctor` fails until `/pilot-wiki`
   repairs it; with entries in the earlier format (`wiki lint` reporting `no-frontmatter`), offer
   `python3 .pilot/pilot.py wiki migrate`. A project with `archInitialized`, `apps` or real content in its
   `PILOT:ARCHITECTURE` block keeps it working; offer `/pilot-architecture --bootstrap`. If `commands` has no
   entry for the project's test, rules, e2e, build, a11y, render or version commands, ask for them and set each with
   `python3 .pilot/pilot.py config set commands.<key> "<cmd>"` (same for `threshold`).

6. **Migrate existing tickets** (when `labels migrate` reports tickets to move).
   Tell the human: `python3 .pilot/pilot.py labels migrate` is the migration step: a dry run that shows how the old
   `status:` and `type:` labels map to the new ones and lists what it cannot map; `--apply` writes. Run the dry run,
   include its output in the report, run `--apply` only if the human agrees, and leave the unmapped tickets to them.
   Also remind them of the CI advice of `/pilot-init` (docs-only paths excluded, no e2e in CI).

7. **Dashboard.** Only with a `dashboardUrl`: after asking, run `/pilot-dashboard --refresh` (reusing
   `$PILOT_SRC`); it republishes at the same address when the template changed. A refusal or failure never blocks
   the rest. Without one, mention that `/pilot-dashboard` can create it.

8. **State.** Set `pilotVersion` to `$PILOT_SRC/VERSION` and `modules` (step 5, only when absent) in
   `.pilot/state.json`; leave every other field alone.

9. **Report.** Version from and to; run `python3 .pilot/pilot.py doctor` and include its result (a failed
   labels check means step 4 did not complete); what was added, updated, orphaned (removed or not), declined,
   and the migration status.
