---
name: pilot-init
description: "One-time bootstrap of a project adopting PILOT: asks for the project name, a short functional vision and the project's own commands, copies the skills, agents, workflows and canonical docs from github.com/Jonas-Eve/pilot, renders CLAUDE.md and README.md from templates, creates the wiki Vision entry when the wiki module is on, adds a default pull request template if none exists, provisions the GitHub labels, and enables the optional modules asked for (wiki, architecture, dashboard, design, proto) with the content language. Refuses to run twice. Use to start using PILOT in a project that has not run it."
argument-hint: "[project name] [functional vision] [--modules wiki,architecture,dashboard,design,proto | --no-modules] [--language en|fr|…]"
disable-model-invocation: true
---

# PILOT bootstrap — `pilot-init`

The one-time setup that makes the rest of PILOT usable in a project. Where this skill is not
available yet, see `README.md`'s "Installing in a project".

## Source

Clone `https://github.com/Jonas-Eve/pilot` once into a scratch directory (`mktemp -d`, or this
session's scratch directory) — call it `$PILOT_SRC` — and use that clone for every step.

## State marker

`.pilot/state.json` at the project root:

```json
{
  "pilotInitialized": true,
  "pilotInitializedAt": "<ISO8601>",
  "pilotVersion": "<$PILOT_SRC/VERSION>",
  "projectName": "<name>",
  "repo": "<owner>/<repo>",
  "language": "en",
  "modules": {"wiki": <bool>, "architecture": <bool>, "dashboard": <bool>, "design": <bool>, "proto": <bool>},
  "commands": {},
  "lastLabelsSyncAt": "<ISO8601>"
}
```

`commands`, `threshold`, `language`, `projectName` and `dashboardUrl` are written with
`python3 .pilot/pilot.py config set <key> <value>`; `/pilot-dashboard` adds `dashboardUrl`,
`dashboardHash` and `dashboardSyncedAt`.

## Steps

1. **Prior run.** If `.pilot/state.json` exists with `pilotInitialized: true`, stop and report:
   PILOT is already initialized ("<projectName>", <pilotInitializedAt>); `/pilot-update` picks up
   PILOT's own changes; the vision is the wiki's `Vision` entry. Write nothing.

2. **Inputs.** Project name and functional vision (2-5 sentences) from the arguments, else ask.
   **Modules** (`.pilot/pilot-process.md` §7): `wiki`, `architecture`, `dashboard`, `design` and `proto`
   (the last two need `dashboard`); `--modules`/`--no-modules`, else ask (recommend `wiki` and `dashboard`
   for a project with a product to describe); a module whose prerequisite is missing brings it along.
   **Language** of wiki and architecture text (`--language`, English by default).
   **The project's commands** the code checks read: `test`, `rules`, `e2e`, `build`, `a11y`, `render`,
   `version` — ask once for those it has, leave the others unset. Optionally the read-size `threshold`
   above which a story is split.

3. **Existing root docs.** If `CLAUDE.md` or `README.md` already exists, never overwrite silently: show what
   would change and ask whether to overwrite or skip that file.

4. **Skills and agents.** Copy every directory of `$PILOT_SRC/.claude/skills/` to `.claude/skills/` and every
   file of `$PILOT_SRC/.claude/agents/` to `.claude/agents/`, verbatim. PILOT-owned from here on, including
   `pilot-init` and `pilot-update`: never hand-edited; `/pilot-update` re-copies them.

5. **Templates.** Render `$PILOT_SRC/assets/templates/CLAUDE.md.tmpl` and `README.md.tmpl`: `{{PROJECT_NAME}}`,
   `{{FUNCTIONAL_VISION}}`, and each `{{PILOT_<NAME>_<CLAUDE|README>}}` placeholder with the verbatim content of
   the matching `pilot-<name>-{claude,readme}.md.tmpl` (INTRO, MAINTENANCE, ARCHITECTURE, COMMANDS), keeping their
   `<!-- PILOT:*:START -->`/`END` markers (`/pilot-update` looks for them). Write to the project root,
   respecting step 3.

6. **PILOT files.** Into `.pilot/` (create it), verbatim, PILOT-owned, `chmod +x` the scripts:
   `$PILOT_SRC/scripts/pilot.py` and `pilot_checks.py`; `$PILOT_SRC/assets/formats.json`;
   `$PILOT_SRC/assets/workflows/*.json` to `.pilot/workflows/`; every `$PILOT_SRC/assets/docs/pilot-*.md`.
   Then `$PILOT_SRC/assets/github/workflows/pilot-status-on-merge.yml` to `.github/workflows/` (it calls
   `pilot.py ticket merged`; without it merged PRs never close their tickets). If a file of that name exists
   and differs, show the diff and ask first.

7. **PR template.** If none of `.github/pull_request_template.md`, `.github/PULL_REQUEST_TEMPLATE.md`,
   `PULL_REQUEST_TEMPLATE.md`, `docs/PULL_REQUEST_TEMPLATE.md` exists, copy
   `$PILOT_SRC/assets/github/pull_request_template.md` to `.github/pull_request_template.md`; if one exists,
   show what would be added and ask. A one-time scaffold: the project's own afterwards, `/pilot-update` never
   touches it.

8. **State and labels.** Write `.pilot/state.json` (schema above; set the commands and threshold with
   `config set`), then `python3 .pilot/pilot.py labels sync` (creates the labels, stamps `lastLabelsSyncAt`).
   If `gh` is unavailable, give the human the command and go on.

9. **Wiki** (module on). If there is no `wiki/`, `python3 .pilot/pilot.py wiki reindex`, then
   `python3 .pilot/pilot.py wiki add product/vision.md --type Vision --title Vision --description "<one sentence>"
   --body "<the vision>"` (in the wiki's language). Project-owned afterwards; for existing work, suggest
   `/pilot-wiki --bootstrap`.

10. **Architecture** (module on). `python3 .pilot/pilot.py arch reindex`; project-owned afterwards. Suggest
    `/pilot-architecture --scaffold` (new apps) or `--bootstrap` (existing ones).

11. **Tell the human, editing nothing of their CI:** exclude the docs-only paths (`wiki/`, `architecture/`)
    from the project's CI (`paths-ignore`), and never run the e2e tests in CI (a script runs them locally).

12. **Report.** Run `python3 .pilot/pilot.py doctor` and include its result; what was created or skipped; offer
    `/pilot-dashboard` when the `dashboard` module is on (publishes a page: only if accepted).
