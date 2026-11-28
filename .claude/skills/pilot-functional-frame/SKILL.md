---
name: pilot-functional-frame
description: "Creates or changes an entry of the project's functional frame: what the product does in shared terms (vision, vocabulary, the rules several behaviors have in common), kept in wiki/. \"<description>\" creates a new entry or changes one; --edit <id> \"<change>\" changes entry <id>; --remove <id> deletes an entry nothing cites. Runs the `functional-frame` workflow (PM leads the discussion, validator, code checks, judge, a gate, one PR); --remove is one PR with no run. Works no ticket. Behaviors are written by /pilot-need, personas by /pilot-persona, user flows by /pilot-user-flow; questions about the wiki are /pilot-wiki."
argument-hint: "\"<description>\" | --edit <id> \"<change>\" | --remove <id>"
disable-model-invocation: true
---

# PILOT functional frame — `pilot-functional-frame`

Read `.pilot/pilot-link-knowledge.md`, `.pilot/pilot-link-wiki.md`, `.pilot/pilot-process.md` and `.pilot/pilot-link-runner.md` first: the runner file says how any workflow runs. Claims no ticket, changes no label.
Run `python3 .pilot/pilot.py doctor --no-wiki` instead of the runner's first step: this skill repairs a missing `wiki/`.

- **Module.** `python3 .pilot/pilot.py module list`: with `wiki` off or `wiki/` missing, say so and propose `python3 .pilot/pilot.py module enable wiki`, then `python3 .pilot/pilot.py wiki reindex`; on a yes go on, on a no stop.

## `"<description>"` and `--edit <id> "<change>"`

Runs the **`functional-frame`** workflow: `python3 .pilot/pilot.py run start functional-frame` (no `--issue`: no ticket is worked), then the runner's loop.

- **Intention.** The `start` step takes the human's text from the argument, else asks. First read what exists (`wiki show vision`, `wiki index --depth 1`, `wiki search` on the description): an entry that already covers it → say so and ask whether to change it instead.
- **`--edit <id>`.** `wiki show <id>` first; the entry's text is part of the intention, the change is the description, and the run updates that id, never adds one. A `Behavior` entry is written by `/pilot-need`, a `Persona` by `/pilot-persona`, a `UserFlow` by `/pilot-user-flow`: point there and stop.
- The run ends by one PR, merged only after its gate.

## `--remove <id>`

1. `wiki show <id>`; tell the human which entries cite it (`backlinks`). A `Behavior` is a product decision, not a button: point at `/pilot-need` and stop; a `Persona` or `UserFlow` goes through `/pilot-persona --remove` or `/pilot-user-flow --remove`.
2. The human confirms; a human is live.
3. `wiki remove <id>` (refused while another entry cites it: change those first). Branch `wiki/remove-<id>`, commit, push, open one PR; never merge it.

## Report

The PR (or "nothing to change"), what is unverified, and what only a human can do.
