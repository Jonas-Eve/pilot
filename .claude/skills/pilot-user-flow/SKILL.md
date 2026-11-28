---
name: pilot-user-flow
description: "Creates, changes or removes a user flow of the wiki (wiki/user-flow/): one journey, which personas play it, each step with its expected observable result; steps no need covers become candidate requests for /pilot-need. \"<description>\" creates one; --edit <id> \"<change>\" changes flow <id>; --remove <id> deletes one. Runs the `user-flow` workflow (QA leads the discussion, PM validates, code checks, judge, a gate, one wiki PR); --remove is one PR with no run. Works no ticket. The flow's personas must exist (/pilot-persona); testing a flow as a persona is /pilot-accept."
argument-hint: "\"<description>\" | --edit <id> \"<change>\" | --remove <id>"
disable-model-invocation: true
---

# PILOT user flow — `pilot-user-flow`

Read `.pilot/pilot-link-knowledge.md`, `.pilot/pilot-link-wiki.md`, `.pilot/pilot-process.md` and `.pilot/pilot-link-runner.md` first: the runner file says how any workflow runs. The `wiki` module must be on (`python3 .pilot/pilot.py module list`), else say so and stop.

Running a user flow as personas is the `accept` workflow: `/pilot-accept <user-flow id> [--persona P]`.

## `"<description>"` and `--edit <id> "<change>"`

Runs the **`user-flow`** workflow: `python3 .pilot/pilot.py run start user-flow` (no ticket), then the runner's loop.

- **Intention.** The `start` step takes the description from the argument, else asks. First read what exists (`wiki show vision`, `wiki index --under persona`, `wiki index --under user-flow`, `wiki search` on the description): a flow that already covers it → say so and ask whether to change it instead.
- **Personas.** A flow lists only existing persona ids; a missing one → point at `/pilot-persona` first and stop.
- **`--edit <id>`.** `wiki show <id>` must be a `UserFlow` (a behavior → `/pilot-need`); its text is part of the intention, the change is the description, and the run updates that id, never adds one.
- Never any credential or secret in an entry. The run ends by one wiki PR that only a human merges; a flow a story owns keeps its status and tickets.

## `--remove <id>`

`wiki show <id>` must be a `UserFlow`. List the entries that cite it (`backlinks`). The human confirms, then `python3 .pilot/pilot.py wiki remove <id>`, branch `wiki/remove-<id>`, commit, push, open one PR. Never merge it.
