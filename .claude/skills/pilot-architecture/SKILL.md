---
name: pilot-architecture
description: "The project's technical frame (architecture/ at the project root, .pilot/pilot-link-architecture.md): overview of the apps, the technical guidelines AIs and developers must respect, and the reference of how the code is built today. No flag, or a question in free text → answers from it with citations (path, status), and says when it does not cover it. --guideline \"<rule>\", --edit <id> \"<change>\" or --accept <id> → runs the technical-frame workflow with the human's intention (its gates decide; one PR). --remove <id> → deletes an entry nothing cites, one PR. --lint → mechanical checks. Never merges a PR outside the workflow's own gate, never claims a ticket. When the module is off it proposes to turn it on first. Use to ask how the project is built, to add or change a rule, or to retire an entry."
argument-hint: "[<question>] | --guideline \"<rule>\" | --edit <id> \"<change>\" | --accept <id> | --remove <id> | --lint"
disable-model-invocation: true
---

# PILOT architecture — `pilot-architecture`

Read `.pilot/pilot-link-knowledge.md` (how to read the bundle) and `.pilot/pilot-link-architecture.md` (layout, statuses) first. Mechanics are in
`python3 .pilot/pilot.py arch …` (`index`, `reindex`, `show`, `lint`, `remove`); run the script, never hand-edit an entry's frontmatter or an `index.md`.
Claims no ticket and changes no label. Run `python3 .pilot/pilot.py doctor --no-wiki` once per session; stop with its report if it fails.

## The module

`python3 .pilot/pilot.py module list` tells whether the `architecture` module is on. Off, or `architecture/` missing: say so and propose
`python3 .pilot/pilot.py module enable architecture`, then `python3 .pilot/pilot.py arch reindex`. On a yes, go on with what was asked; on a no, stop.

## Question (no flag)

1. Read per `.pilot/pilot-link-knowledge.md`: `arch index --depth 1`, then `arch search` or a folder, then `arch show` only those that bear on the question (`--all` for history).
2. Answer from them, citing each as its `path` and status. A `proposed` entry is not yet a rule: say so; a `superseded` one is history, point at its successor.
   Where the architecture is silent, say it is not covered; do not fill the gap from the code.
   Asked for a global ADR: there is none in the technical frame; ADRs are local, written by the plan workflow.

## `--guideline "<rule>"`, `--edit <id> "<change>"`, `--accept <id>`

One thing: the `technical-frame` workflow, run per `.pilot/pilot-link-runner.md`, led by the persona its data names. It works no ticket (the runner creates a `run` issue).
- Its intention is the human's text: the rule, or the change to entry `<id>` (`arch show <id>` first; a `superseded` entry is history, say so and stop), or, for `--accept`, the wish to put the `proposed` entry `<id>` in force.
  No flag with an intention in free text is the same run. Ask the human for the intention when none was given.
- Specific to it: the run ends by one PR, merged only after its second gate; the gates replace any separate acceptance.

## `--remove <id>`

1. `arch show <id>`; tell the human which entries cite it (`backlinks`). The root `overview.md` is never removed (edit it through the workflow); an app's own overview only when the app is gone.
2. The human confirms; a human is live.
3. `arch remove <id>` (refused while another entry cites it: edit those first). Branch `architecture/remove-<id>`, commit, push, open one PR; never merge it.

## `--lint`

`arch lint`. Report its findings (unreadable entry, duplicate id, stale index); fix none silently. Fixes go in a branch `architecture/lint-<YYYY-MM-DD>` and one PR; nothing to change → no PR.

`--adr`, `--verify`, `--bootstrap` and `--scaffold` do not exist for now: say so if asked.

## Wrap-up

Report the PR (or "nothing to change") and what is left for the human.
