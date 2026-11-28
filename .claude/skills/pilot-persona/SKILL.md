---
name: pilot-persona
description: "Creates, changes or removes a persona of the wiki (wiki/persona/): who an end user is, their goals, constraints and way of using the product, used to steer a Recette. \"<description>\" creates one; --edit <id> \"<change>\" changes persona <id>; --remove <id> deletes one nothing cites. Runs the `persona` workflow (designer leads the discussion, PM validates, code checks, judge, a gate, one wiki PR); --remove is one PR with no run. Works no ticket. A user flow is /pilot-user-flow; testing a flow as a persona is /pilot-accept."
argument-hint: "\"<description>\" | --edit <id> \"<change>\" | --remove <id>"
disable-model-invocation: true
---

# PILOT persona — `pilot-persona`

Read `.pilot/pilot-link-knowledge.md`, `.pilot/pilot-link-wiki.md`, `.pilot/pilot-process.md` and `.pilot/pilot-link-runner.md` first: the runner file says how any workflow runs. The `wiki` module must be on (`python3 .pilot/pilot.py module list`), else say so and stop.

## `"<description>"` and `--edit <id> "<change>"`

Runs the **`persona`** workflow: `python3 .pilot/pilot.py run start persona` (no ticket), then the runner's loop.

- **Intention.** The `start` step takes the description from the argument, else asks. First read what exists (`wiki show vision`, `wiki index --under persona`): a persona that already covers it → say so and ask whether to change it instead.
- **`--edit <id>`.** `wiki show <id>` must be a `Persona`; its text is part of the intention, the change is the description, and the run updates that id, never adds one.
- Never any credential or secret in an entry. The run ends by one wiki PR that only a human merges.

## `--remove <id>`

`wiki show <id>` must be a `Persona`. List the entries that cite it (`backlinks`; a flow's `Personas:` line counts): a persona a flow names is not removed until that flow is changed (`/pilot-user-flow --edit`). The human confirms, then `python3 .pilot/pilot.py wiki remove <id>`, branch `wiki/remove-<id>`, commit, push, open one PR. Never merge it.
