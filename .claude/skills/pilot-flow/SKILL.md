---
name: pilot-flow
description: "Drafts, revises or removes a persona (wiki/persona/) or a user flow (wiki/user-flow/) with a human. --new persona|flow runs the `personas-flows` workflow (auditor, writer, validator, checks, judge, a review gate, one wiki PR); --edit <id> revises one the same way; --remove <id> deletes one (human decision). Works no ticket. Testing a flow as personas is /pilot-accept."
argument-hint: "--new persona|flow <description> | --edit <id> \"<change>\" | --remove <id>"
disable-model-invocation: true
---

# PILOT flow — `pilot-flow`

Read `.pilot/pilot-link-knowledge.md`, `.pilot/pilot-link-wiki.md`, `.pilot/pilot-process.md` and `.pilot/pilot-link-runner.md` first: the runner file says how any workflow runs. The `wiki` module must be on (`python3 .pilot/pilot.py module list`), else say so and stop.

`pilot-flow <flow> --as <persona>` no longer exists: running a user flow as personas is the `accept` workflow, `/pilot-accept <user-flow id> [--persona P]`. Say so if asked.

## `--new persona|flow <description>` and `--edit <id> "<change>"`

Runs the **`personas-flows`** workflow: `python3 .pilot/pilot.py run start personas-flows` (no ticket), then the runner's loop.

- **Intention.** The `start` step takes the description (persona: entry 1; flow: entry 2) from the argument, else asks. First read what exists (`.pilot/pilot-link-knowledge.md`): `wiki show vision`, `wiki index --under persona`, `wiki index --under user-flow`, and for a flow `wiki search` on the description. An entry that already covers it → say so and ask whether to revise it instead.
- **`--edit <id>`.** `wiki show <id>` must be a `Persona` or a `UserFlow` (a behavior → `/pilot-wiki --edit`); the entry's text is part of the intention, the change is the description, and the run updates that id, never adds one.
- **A flow** lists only existing persona ids; a missing one → offer `--new persona` first and stop.
- Never any credential or secret in an entry. The run ends by one wiki PR that only a human merges; a flow a story owns keeps its status and tickets.

## `--remove <id>`

`wiki show <id>` must be a `Persona` or a `UserFlow`. List the entries that cite it (`backlinks`; a flow's `Personas:` line counts): a persona a flow names is not removed until that flow is revised (`--edit`). The human confirms, then `python3 .pilot/pilot.py wiki remove <id>`, branch `wiki/remove-<id>`, commit, push, open one PR. Never merge it.
