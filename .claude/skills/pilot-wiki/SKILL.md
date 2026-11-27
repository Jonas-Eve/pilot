---
name: pilot-wiki
description: "The project's wiki (wiki/ at the project root, .pilot/pilot-link-wiki.md): the source of truth for what the product does and what is promised, read by agents and humans. No flag, or a question in free text → answers from the wiki with citations (path, status), and says when the wiki does not cover it. --edit <id> \"<change>\" → runs the functional-frame workflow with the human's intention (its gate decides; one PR). --remove <id> → deletes an entry nothing cites, one PR. --lint → mechanical checks. Entries of need (behaviors) are written by /pilot-need, not here. Never claims a ticket. When the wiki module is off it proposes to turn it on first. Use to ask what the product does, to correct the functional frame, or to retire an entry."
argument-hint: "[<question>] | --edit <id> \"<change>\" | --remove <id> | --lint"
disable-model-invocation: true
---

# PILOT wiki — `pilot-wiki`

Read `.pilot/pilot-link-knowledge.md` (how to read the bundle) and `.pilot/pilot-link-wiki.md` (entry format, statuses) first. Mechanics are
in `python3 .pilot/pilot.py wiki …` (`index`, `reindex`, `show`, `status`, `lint`, `add`, `set`, `remove`); run the script, never hand-edit an entry's
frontmatter or an `index.md`. Claims no ticket and changes no label. Run `python3 .pilot/pilot.py doctor --no-wiki` once per session (the wiki check is the one this skill
repairs); stop with its report if it fails.

## The module

`python3 .pilot/pilot.py module list` tells whether the `wiki` module is on. Off, or `wiki/` missing: say so and propose
`python3 .pilot/pilot.py module enable wiki`, then `python3 .pilot/pilot.py wiki reindex`, which creates `wiki/` with its root `index.md`.
On a yes, go on with what was asked; on a no, stop.

## Question (no flag)

1. Read per `.pilot/pilot-link-knowledge.md`: `wiki index --depth 1`, then `wiki search` or a folder, then `wiki show` only those that bear on the question.
2. Answer from them, citing each as its `path` with its `display` status. A `proposed`/`specified` entry is a promise, not behavior: say so.
   Where the wiki is silent, say it is not covered; do not fill the gap from the code.

## `--edit <id> "<change>"`

The `functional-frame` workflow, run per `.pilot/pilot-link-runner.md`, led by the persona its data names. It works no ticket (the runner creates a `run` issue).
- Its intention is the human's text: the change to entry `<id>` (`wiki show <id>` first); ask the human for it when none was given. A free-text intention with no id is the same run.
- A `Persona` or `UserFlow` entry → point at `/pilot-flow --edit <id> "<change>"` and stop. An entry of need (a behavior) is not written here: that is the `need` workflow, `/pilot-need`; say so and stop.
- Specific to it: the run ends by one PR, merged only after its gate.

## `--remove <id>`

1. `wiki show <id>`; tell the human which entries cite it (`backlinks`). A `Persona` or `UserFlow` is removed once nothing cites it (a flow's `Personas:` line counts: revise that flow with `/pilot-flow --edit` first).
   An entry of need is a product decision, not a button: point at `/pilot-need` and stop.
2. The human confirms; a human is live.
3. `wiki remove <id>` (refused while another entry cites it: edit those first). Branch `wiki/remove-<id>`, commit, push, open one PR; never merge it.

## `--lint`

`wiki lint`. Report its findings (unreadable entry, duplicate id, orphaned promise, …); fix none silently. Fixes go in a branch `wiki/lint-<YYYY-MM-DD>` and one PR; nothing to change → no PR.

`--bootstrap` does not exist for now: say so if asked.

## Wrap-up

Report the PR (or "nothing to change") and what is left for the human.
