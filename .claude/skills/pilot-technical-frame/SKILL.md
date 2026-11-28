---
name: pilot-technical-frame
description: "Creates, changes, accepts or removes an entry of the project's technical frame: how the code is built (stack, structure, guidelines AIs and developers must respect), kept in architecture/. \"<rule>\" or --guideline \"<rule>\" creates a guideline; --edit <id> \"<change>\" changes entry <id>; --accept <id> puts a proposed entry in force; --remove <id> deletes an entry nothing cites. Runs the `technical-frame` workflow (architect leads the discussion, validator, code checks, judge, a first gate on the rule, then its implementation, a second gate, one PR); --remove is one PR with no run. Works no ticket; ADRs are written by /pilot-plan; questions about the architecture are /pilot-architecture."
argument-hint: "\"<rule>\" | --guideline \"<rule>\" | --edit <id> \"<change>\" | --accept <id> | --remove <id>"
disable-model-invocation: true
---

# PILOT technical frame — `pilot-technical-frame`

Read `.pilot/pilot-link-knowledge.md`, `.pilot/pilot-link-architecture.md`, `.pilot/pilot-process.md` and `.pilot/pilot-link-runner.md` first: the runner file says how any workflow runs. Claims no ticket, changes no label.
Run `python3 .pilot/pilot.py doctor --no-wiki` instead of the runner's first step.

- **Module.** `python3 .pilot/pilot.py module list`: with `architecture` off or `architecture/` missing, say so and propose `python3 .pilot/pilot.py module enable architecture`, then `python3 .pilot/pilot.py arch reindex`; on a yes go on, on a no stop.

## `"<rule>"`, `--guideline "<rule>"`, `--edit <id> "<change>"`, `--accept <id>`

Runs the **`technical-frame`** workflow: `python3 .pilot/pilot.py run start technical-frame` (no `--issue`: no ticket is worked), then the runner's loop.

- **Intention.** The human's text: the rule, or the change to entry `<id>` (`arch show <id>` first; a `superseded` entry is history, say so and stop), or, for `--accept`, the wish to put the `proposed` entry `<id>` in force. A free text with no flag is the same run; ask for the intention when none was given. An ADR is not written here: point at `/pilot-plan`.
- Specific to it: the run ends by one PR, merged only after its second gate; the gates replace any separate acceptance.

## `--remove <id>`

1. `arch show <id>`; tell the human which entries cite it (`backlinks`). The root `overview.md` is never removed (change it through the workflow); an app's own overview only when the app is gone.
2. The human confirms; a human is live.
3. `arch remove <id>` (refused while another entry cites it: change those first). Branch `architecture/remove-<id>`, commit, push, open one PR; never merge it.

## Report

The PR (or "nothing to change"), what is unverified, and what only a human can do.
